---
name: hermes-stuck-turn-diagnosis
description: Diagnose Hermes gateway turns that show “Still working...” for an unusually long time and distinguish a real long-running task from a stalled/hung turn.
version: 1.0.0
metadata:
  hermes:
    tags: [hermes, gateway, discord, diagnostics, stuck-turns, hung-requests]
    related_skills: [systematic-debugging, hermes-agent, discord-gateway-profile-drift-diagnosis]
---

# Hermes stuck turn diagnosis

Use this when a user reports a Discord or gateway message like:
- `Still working...`
- `20 min elapsed — iteration 1/90`
- progress text claims tools are running, but no answer arrives

Goal: determine whether the turn is actually making progress or is stalled.

## Core insight

A long-running Hermes turn is not automatically abnormal. But if all of the following are true, treat it as a likely stalled turn:
- the inbound message exists in `agent.log`
- there is no later `response ready` for that same chat/thread
- the session file stops updating
- the worker child process remains alive but mostly idle
- process state shows sleep/wait (`futex_wait_queue`, `ep_poll`, etc.) rather than active CPU work

In that case, the UI progress line can be stale/misleading: it may still show the last known tool names even though the turn is no longer progressing.

## Read-only workflow

### 1. Confirm gateway is still alive
Run:
```bash
systemctl --user show hermes-gateway-<profile>.service -p MainPID,ActiveState,SubState,Result
ps -ef | grep 'hermes_cli.main --profile <profile>' | grep -v grep
```

Interpretation:
- gateway `active/running` means the whole bot is not down
- one extra child process under the gateway PID often indicates an active or recently active turn

### 2. Correlate the reported thread with logs
Search `agent.log` for the relevant chat/thread ID or the user message text:
```bash
search_files(
  pattern="<thread_id OR unique message text>",
  path="/home/ubuntu/.hermes/profiles/<profile>/logs",
  target="content",
  output_mode="content",
  context=1,
)
```

Look for this sequence:
- `inbound message: ...`
- optional tool/memory/auxiliary initialization lines
- expected normal end state: `response ready: ...`

If `inbound message` exists but `response ready` does not appear afterward, the turn is suspicious.

### 3. Inspect session freshness
Check the relevant session files under:
- `.../sessions/sessions.json`
- `.../sessions/session_<id>.json`
- `.../<session_id>.jsonl`

Useful checks:
```bash
python3 - <<'PY'
import os, glob, time
for p in sorted(glob.glob('/home/ubuntu/.hermes/profiles/<profile>/sessions/*'), key=os.path.getmtime, reverse=True)[:15]:
    st=os.stat(p)
    print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)), st.st_size, p)
PY
```

Interpretation:
- if the relevant session file stopped updating near the time of the inbound message, there is no continuing progress
- if the progress UI says it is still running but file mtimes are frozen, treat the UI as stale

### 4. Inspect worker process state
Check the parent and child PIDs:
```bash
ps -o pid,ppid,etime,%cpu,%mem,stat,wchan:32,cmd -p <parent_pid>,<child_pid>
sed -n '1,40p' /proc/<pid>/status
cat /proc/<pid>/syscall 2>/dev/null || true
```

High-value signals:
- parent in `ep_poll` and child in `futex_wait_queue`
- very low CPU for many minutes
- child elapsed time roughly matching the stuck duration

Interpretation:
- sleeping/waiting states + no CPU + no file updates strongly suggest stall/hang, not active reasoning

### 5. Check socket state only as supporting evidence
```bash
ss -tpn | grep <pid> || true
```

Interpretation:
- `CLOSE-WAIT` or a small number of idle `ESTAB` connections can support the diagnosis
- do not rely on sockets alone; use them only with log/session/process evidence

## Classification guide

### Healthy long turn
Classify as healthy-but-slow if most of these are true:
- session files continue updating
- CPU or tool activity is still changing
- new logs continue appearing for the same turn
- `response ready` eventually appears

### Stalled / hung turn
Classify as stalled if most of these are true:
- inbound message logged
- no `response ready`
- session file mtime frozen
- child process still exists but is idle/sleeping
- progress UI remains on the same iteration/tool list for an unusually long time

## Recovery workflow after approval

Only do this after the user explicitly approves write-side action.

### Preferred recovery: force a clean service restart via systemd
Observed on this host:
- a normal `systemctl --user restart hermes-gateway-<profile>.service` may hang long enough to time out from the caller side when the stuck turn does not drain
- sending `SIGTERM` to the stuck child PID can trigger the parent gateway to begin shutdown, but may still wait for drain and not clear quickly
- the reliable escape hatch was:

```bash
systemctl --user kill -s SIGKILL hermes-gateway-<profile>.service
```

Then wait for systemd auto-restart (`Restart=on-failure`, often `RestartSec=30`) and verify fresh startup.

### Verify recovery
Check all of these:
```bash
systemctl --user show hermes-gateway-<profile>.service -p MainPID,ActiveState,SubState,Result,ExecMainStatus
systemctl --user status hermes-gateway-<profile>.service --no-pager | sed -n '1,50p'
ps -ef | grep 'hermes_cli.main --profile <profile>' | grep -v grep
```

In logs, require fresh lines such as:
- `Starting Hermes Gateway...`
- `Connected as ...`
- `Gateway running with ...`

Interpretation:
- new `MainPID` + fresh `Connected as` means the stuck turn has been cleared by restart
- if the old PID persists for a while during shutdown, wait through the configured restart window before classifying recovery as failed

## Recommended wording to user

Prefer concise reporting like:
- gateway itself is still running
- this specific turn appears stalled rather than actively progressing
- the `Still working...` line is likely stale progress state, not proof of active work
- if approved, the stuck turn can usually be cleared by restarting the gateway service

## Pitfalls

- Do not conclude a full bot outage from one stuck turn.
- Do not conclude health from the UI progress line alone.
- Do not kill/restart anything without approval; recovery is a write-side action.
- Distinguish a genuinely expensive investigation from a frozen turn by checking log progression and session mtimes.
- Do not assume `kill -TERM <child_pid>` only affects the child; in this environment it can cause the main gateway to start shutdown as well.
- Do not assume a timed-out `systemctl restart` means nothing happened; re-check service state, logs, and jobs before retrying with a stronger action.
