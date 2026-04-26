---
name: discord-gateway-profile-drift-diagnosis
description: Diagnose Discord mention/thread behavior when runtime process/config drift makes behavior differ from expected adapter logic.
version: 1.0.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [discord, gateway, diagnostics, profiles, configuration, runtime-drift]
---

# Discord gateway profile drift diagnosis

Use this when a Discord bot responds in unexpected places or with unexpected mention/thread behavior, especially when the adapter code already appears to support the desired behavior.

Typical symptoms:
- Bot responds without mention in normal channels
- Bot should only continue without mention inside threads it already joined
- Multiple configs or profiles may exist
- User-reported behavior does not match the config file you first inspected

## Core insight

For Discord mention/thread bugs, the root cause is often **runtime drift**, not adapter logic:
- multiple gateway processes active at once
- wrong profile launched
- default config and profile config disagree
- runtime overrides hide the effective value
- the user is observing a different channel/process than the one you inspected

Do not patch code first. Prove which runtime instance owns the behavior.

## Workflow

1. Load relevant debugging guidance
   - Load `systematic-debugging` before changing anything.

2. Inspect Discord adapter behavior in code
   - Read `gateway/platforms/discord.py`
   - Confirm these areas:
     - mention gate in `_handle_message()`
     - thread participation bypass (`ThreadParticipationTracker`)
     - auto-thread creation behavior
     - send/reply behavior when `thread_id` is present
   - Also inspect `gateway/session.py` for `build_session_key()`.

3. Verify whether desired semantics are already implemented
   Expected good-state behavior:
   - normal channel: `require_mention=true` means no response without mention
   - mention in channel: bot can auto-create a thread
   - participated thread: follow-up messages can proceed without mention
   - `thread_sessions_per_user=false` means one shared session per thread

4. Check live runtime, not just files
   - List gateway-related processes.
   - Inspect each process command line.
   - Identify whether multiple gateway instances are running.
   - Note which instance uses an explicit profile and which uses default config.

5. Inspect all candidate configs
   Read all plausible active configs, including:
   - default global config
   - profile-specific configs for the relevant bots
   Look for:
   - `discord.require_mention`
   - `discord.free_response_channels`
   - `discord.allowed_channels`
   - `discord.auto_thread`
   - Discord home channel settings

6. Check effective overrides safely
   - Verify whether Discord runtime variables are set, but avoid storing or copying secrets.
   - Inspect config loading code to confirm which YAML keys become runtime values.

7. Confirm channel identity
   - Inspect channel directory or config references for the observed Discord channel IDs.
   - Distinguish home channel, allowed channel, free-response channel, and actual user-observed channel.
   - Do not assume the home channel is the place where gating is failing.

8. Form the diagnosis before proposing edits
   Common outcomes:
   - adapter code already matches desired behavior
   - issue caused by a free-response channel in the active config
   - issue caused by wrong profile being active
   - issue caused by two active gateway processes with different configs

## Fast interpretation guide

If you find:
- `require_mention: true`
- `free_response_channels` contains the active channel ID

Then the bot will respond without mention there by design.

If you find:
- one process with an explicit profile
- another plain gateway process without that profile

Then user-visible behavior may come from the wrong process/config pair.

If `build_session_key()` shows:
- thread IDs included
- `thread_sessions_per_user=False`

Then thread conversations are already one-thread-one-session by default.

## Recommended remediation order

1. stop runtime ambiguity first
   - keep only the intended gateway/profile process active
2. normalize config in the active profile
   - `discord.require_mention: true`
   - empty `discord.free_response_channels` unless explicitly desired
   - `discord.auto_thread: true`
3. only then patch code if live behavior still contradicts the verified active config
4. add regression tests if code is changed

## Reporting template

Report in this order:
1. whether code already implements the requested behavior
2. which processes are actually running
3. which config each likely uses
4. whether overrides are affecting the live result
5. exact minimal fix needed
6. whether a write approval token is required before applying the fix

## Pitfalls

- Do not assume the profile named in conversation is the one serving traffic.
- Do not assume the home channel is the response channel.
- Do not patch `SOUL.md`.
- Do not edit configs until the user gives the required approval token.
- Do not claim a code bug when runtime drift already explains the symptom.
