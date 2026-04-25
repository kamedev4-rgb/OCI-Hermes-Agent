---
name: myknot-discord-thread-session-continuity
description: Diagnose and improve MyKNOT same-thread conversation continuity across gateway restarts, idle resets, and daily session resets.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [myknot, discord, threads, sessions, continuity, restart, gateway]
    related_skills: [systematic-debugging, daily_check, discord-gateway-profile-drift-diagnosis]
---

# MyKNOT Discord thread session continuity

Use this when the user asks whether MyKNOT can keep talking in the same Discord thread after a restart, or why a same-thread conversation feels reset.

## Scope

Read-only diagnosis and design guidance unless explicit write authorization is available.
Do not modify `SOUL.md`.
Do not connect to MyKNOT directly; inspect local code, config, logs, and PostgreSQL/SQLite state.

## Core findings

Same Discord thread continuity is already partially supported by the current architecture.
The missing behavior is usually not thread identification, but **session reset policy** and **lack of automatic reattachment to an old session ID**.

### Important implementation facts

1. Session identity is thread-based for Discord threads.
   - File: `gateway/session.py`
   - Function: `build_session_key()`
   - Group/thread behavior:
     - thread keys include both `chat_id` and `thread_id`
     - with `thread_sessions_per_user=False` (default), a Discord thread is one shared session for all participants in that thread
   - Typical key format:
     - `agent:main:discord:thread:<channel_id>:<thread_id>`

2. The session-key to session-id mapping is persisted.
   - File: `gateway/session.py`
   - `SessionStore` loads/saves `sessions.json`
   - Typical path:
     - `~/.hermes/profiles/myknot/sessions/sessions.json`

3. Conversation history is persisted and reloadable.
   - File: `gateway/session.py`
   - `load_transcript(session_id)` loads from SQLite first, JSONL as fallback, and prefers the longer source
   - File: `gateway/run.py`
   - `_handle_message_with_agent()` calls `history = self.session_store.load_transcript(session_entry.session_id)` before running the agent

4. Manual restore already exists.
   - File: `gateway/run.py`
   - `/resume` is implemented in `_handle_resume_command()`
   - File: `gateway/session.py`
   - `switch_session(session_key, target_session_id)` re-points the live session key to an old session so the old transcript loads again

5. The main blocker is reset policy.
   - Config file: `~/.hermes/profiles/myknot/config.yaml`
   - Check:
     - `session_reset.mode`
     - `session_reset.idle_minutes`
     - `session_reset.at_hour`
     - `group_sessions_per_user`
     - `discord.auto_thread`
   - If `session_reset.mode: both`, the same thread can still be moved to a fresh `session_id` after idle timeout or the daily reset window

## Diagnostic workflow

### 1. Confirm live runtime

Check service state:
```bash
systemctl --user show hermes-gateway-myknot.service -p ActiveState,SubState,MainPID,ExecMainStartTimestamp
```

Expected for healthy runtime:
- `ActiveState=active`
- `SubState=running`

### 2. Check MyKNOT config relevant to continuity

Read:
- `~/.hermes/profiles/myknot/config.yaml`

Look for:
- `discord.auto_thread: true`
- `group_sessions_per_user: true`
- `thread_sessions_per_user` if present
- `session_reset.mode`
- `session_reset.idle_minutes`
- `session_reset.at_hour`

Interpretation:
- `group_sessions_per_user: true` is fine
- thread continuity depends primarily on `build_session_key()` and whether resets create a fresh session
- `session_reset.mode: both` means same thread does **not** guarantee same conversation

### 3. Inspect logs for thread/session behavior

Search MyKNOT logs for:
- `inbound message:`
- `response ready:`
- `Agent cache idle-TTL evict`
- `Session expiry:`
- `Pre-reset memory flush completed`
- `Received SIGTERM/SIGINT`
- `Starting Hermes Gateway`

What to prove:
- same Discord thread ID keeps receiving messages after restart
- but session expiry or idle eviction occurs
- if reset notifications appear, continuity breaks by design rather than by bug

### 4. Inspect persisted session mapping

Check that `sessions.json` exists and contains Discord thread keys:
- `~/.hermes/profiles/myknot/sessions/sessions.json`

What this proves:
- the system already has durable thread-key mapping infrastructure
- a restart alone does not necessarily erase the ability to reconnect the thread to a prior session

### 5. Inspect transcript persistence

Check `state.db` schema or use Python sqlite3 if `sqlite3` CLI is missing.

Useful Python snippet:
```bash
python3 - <<'PY'
import sqlite3
path='/home/ubuntu/.hermes/profiles/myknot/state.db'
con=sqlite3.connect(path)
cur=con.cursor()
cur.execute("select name from sqlite_master where type='table' order by name")
print(cur.fetchall())
PY
```

Expected important tables:
- `sessions`
- `messages`

What this proves:
- transcript restoration is technically possible because prior messages are retained

### 6. Inspect code path for message handling

Read these files:
- `gateway/session.py`
- `gateway/run.py`

Focus on:
- `build_session_key()`
- `SessionStore.get_or_create_session()`
- `SessionStore.switch_session()`
- `SessionStore.load_transcript()`
- `_handle_message_with_agent()`
- `_handle_resume_command()`

## Interpretation guide

### Case A: restart only, no session reset

If:
- same `session_key` still points to same `session_id`
- transcript exists
- `load_transcript()` runs

Then same-thread continuation should already work.

### Case B: idle reset or daily reset fires

If:
- `session_reset.mode` is `idle`, `daily`, or `both`
- `get_or_create_session()` decides the session is stale
- a new `session_id` is created

Then the same thread will still exist, but conversation continuity is broken by policy.

### Case C: manual recovery already possible

If `/resume` can restore the prior session, then the missing feature is **automatic resume selection**, not transcript persistence.

## Recommended remediation order

### Option 1: configuration-only

Best when the user only wants fewer resets.

Adjust `session_reset` to be less aggressive, for example:
- larger `idle_minutes`
- disable daily resets if they are not needed
- or set `mode: none` if the trade-offs are acceptable

Risk:
- larger transcripts and more context growth over time

### Option 2: minimal code change

Goal:
- preserve same-thread continuity across normal gateway restart
- without changing explicit `/reset` or `/stop` semantics

Approach:
1. keep using the persisted `session_key -> session_id` mapping from `sessions.json`
2. on restart, do not force a fresh session for the same Discord thread unless reset policy explicitly requires it
3. rely on existing `load_transcript()` to rehydrate context

### Option 3: automatic same-thread reattach after reset

Goal:
- even after auto-reset, optionally restore the immediately previous session for the same Discord thread

Approach:
1. when `get_or_create_session()` would create a fresh session because of idle/daily policy
2. look up the most recent prior session for the same `session_key`
3. if safe, call `switch_session()` automatically instead of staying on the new session

Safety checks:
- do not auto-reattach after explicit `/stop`
- do not auto-reattach after explicit `/reset`
- require that the prior session actually has transcript history
- optionally require a freshness window

## Design recommendation for MyKNOT

Prefer this order:
1. reduce or clarify `session_reset` first
2. verify whether restart-only continuity is already adequate
3. only then implement automatic reattachment logic

Reason:
- the current architecture already has almost all required persistence primitives
- the behavioral gap is mostly policy and session selection
- this avoids unnecessary invasive changes

## Reporting template

Report in this order:
1. whether the same Discord thread already maps to a stable thread-based session key
2. whether session mapping is persisted across restart
3. whether transcript storage is persisted and reloadable
4. whether reset policy is the true reason continuity breaks
5. whether `/resume` already proves restoration is possible
6. minimal recommended change: config-only, minimal code, or auto-reattach

## Pitfalls

- Do not confuse `Agent cache idle-TTL evict` with transcript loss. Cache eviction alone does not prove transcript loss.
- Do not assume restart is the root cause when `session_reset.mode: both` is active.
- Do not claim the feature is impossible when `/resume` and `switch_session()` already exist.
- Do not forget that Discord thread sessions are typically shared among participants when `thread_sessions_per_user=False`.
- Do not modify `SOUL.md`.
