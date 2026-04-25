---
name: hermes-discord-gateway-setup
description: Configure Hermes Agent for Discord, including bot setup, gateway service management, mention behavior, and verification.
version: 1.0.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, discord, gateway, setup, systemd]
    related_skills: [systematic-debugging]
---

# Hermes Discord Gateway Setup

Use when the user wants to run Hermes through Discord.

## Scope

This skill covers:
- checking readiness
- configuring Discord bot access
- starting the messaging gateway as a persistent service
- enabling mention-free behavior in selected channels
- verifying that the bot can reach Discord successfully

## Recommended flow

### 1. Check readiness

Run:

```bash
source venv/bin/activate && hermes doctor
source venv/bin/activate && hermes gateway status
```

Inspect Discord-related settings in the user's Hermes configuration if needed.

### 2. Confirm Discord-side setup

The user should have already done the following in Discord Developer Portal:

1. created an application
2. created a bot
3. enabled Message Content Intent
4. invited the bot with scopes:
   - `bot`
   - `applications.commands`
5. granted at least:
   - Send Messages
   - Read Message History
   - Attach Files

### 3. Configure bot access

Prefer the interactive command:

```bash
source venv/bin/activate && hermes gateway setup
```

If the environment must be updated manually, avoid exposing secrets in the transcript and use a local-only edit path.

The important values are:
- bot token
- allowed Discord user IDs or role IDs
- optional home channel ID for proactive delivery

### 4. Install and run the gateway as a user service

On Linux, use:

```bash
source venv/bin/activate && hermes gateway install
source venv/bin/activate && hermes gateway start
source venv/bin/activate && hermes gateway status
```

Expected result:
- service installed
- service enabled
- linger enabled so it survives logout
- service active and running

### 5. Configure mention behavior

Default behavior:
- DMs do not need mentions
- server channels require mentions

For one or more mention-free channels, keep mention requirement globally enabled and set only the selected free-response channels in Hermes config.

Recommended pattern:
- keep `require_mention: true`
- populate `free_response_channels` with the specific channel IDs that should allow normal conversation without tagging the bot

Then restart the gateway.

### 6. Custom command note

If the user wants a Discord command that returns fixed output directly, consider Hermes `quick_commands` in `config.yaml` rather than prompt changes.

Operational detail worth remembering:
- `quick_commands` work through the Discord gateway
- they are available when typed manually
- they do not appear in Discord's auto-registered slash-command picker/help tables
- for persona-inspection commands like `/soul`, verify which SOUL file the user actually means before wiring the command

Path pitfall discovered in practice:
- the base SOUL file can still contain the default or generic identity text
- the user may actually expect a persona-specific SOUL file under the personas directory
- if `/soul` returns unexpected template text, inspect both the base SOUL and the persona-specific SOUL, then point the quick command at the file the user expects

Session-cache pitfall discovered in practice:
- editing the base SOUL/persona file and then running `/restart` is not enough to update an existing Discord conversation
- the gateway restart only restarts the process; it does not create a fresh conversation session for that chat/thread
- Discord sessions keep the previous `session_id` and cached system prompt until the user sends `/new` or `/reset`
- so the reliable sequence for persona/system-prompt changes is:
  1. update the intended SOUL file
  2. run `/restart` (or `hermes gateway restart`)
  3. in Discord, send `/new` or `/reset` in the same chat/thread
  4. then send the next normal message
- if behavior still looks stale, inspect the session mapping and the matching saved session transcript to confirm whether the `session_id` changed and whether the stored `system_prompt` reflects the new SOUL content

Profile-isolation pitfall discovered in practice:
- if the user asks about another Hermes persona/profile (for example a sibling Discord worker like `mycare`), `session_search` and the current profile memory may return nothing even though the other profile is configured correctly
- do not conclude "it is not defined" from the active profile alone
- inspect the sibling profile directory directly under `~/.hermes/profiles/<name>/`
- high-signal files to check are:
  - `SOUL.md` → identity/role of that profile
  - `config.yaml` → Discord channels, commands, and profile-local behavior
  - `sessions/sessions.json` → whether Discord threads are being mapped as `chat_type: thread`
  - `cron/jobs.json` → autonomous jobs and delivery targets
  - `channel_directory.json` → channel naming/ID hints when available
- this is the reliable way to verify whether a separate Discord-facing Hermes persona exists and how it is wired

### 7. Verify

Use:

```bash
source venv/bin/activate && hermes gateway status
journalctl --user -u hermes-gateway -n 80 --no-pager
```

If needed, validate externally that:
- the bot token is valid
- the configured home channel is reachable

## Pitfalls

### Restart shows `status=75/TEMPFAIL`
A restart can briefly show `status=75` during turnover. Do not assume failure immediately.

Wait a few seconds and check status again. If needed, run:

```bash
source venv/bin/activate && hermes gateway start
```

Then verify with `hermes gateway status`.

### `No messaging platforms enabled`
Usually means the Discord configuration did not load as expected. Re-check the Hermes configuration source and restart the gateway.

### Slash command sync timeout
A Discord slash-command sync timeout warning is not automatically fatal. Treat it as non-fatal unless normal chat behavior also fails.

## Success criteria

The setup is successful when:
- the gateway service is running
- Discord bot access is configured
- the user can DM the bot or use it in server channels
- selected free-response channels work without mentions
- other channels still require mentions if that is the intended policy
