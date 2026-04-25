---
name: mycare-llm-free-monitor-timer
description: Replace a fragile Hermes cron monitor job with an LLM-free systemd user timer that runs a Python monitor script directly and posts to Discord only on actionable events.
version: 1.0.0
metadata:
  hermes:
    tags: [mycare, cron, systemd, discord, monitoring, llm-free, ops]
    related_skills: [hermes-cron-failure-audit, hermes-agent]
---

# MyCARE LLM-free Monitor Timer

Use when a MyCARE/MyKNOT monitor job is simple and deterministic, but a Hermes cron job is failing because the final LLM turn is unnecessary and fragile.

Typical trigger:
- a cron job runs a script every few minutes
- the script output is enough to decide whether to notify
- most runs should be silent
- failures show provider/API errors even though the script output is healthy

## When this pattern is appropriate

Good fit:
- Docker/container heartbeat checks
- service/process up/down checks
- simple resource threshold monitors
- restart-on-failure monitors where notification content is deterministic

Bad fit:
- multi-source diagnosis
- human-readable summaries that need synthesis
- jobs where you really want the agent to interpret logs or correlate signals

## Why switch away from Hermes cron

Hermes cron always builds a prompt and runs an agent turn. For simple monitors this creates unnecessary failure modes:
- provider/API outages
- accidental skill loads
- extra tokens to decide whether to emit `[SILENT]`

If the monitor logic is deterministic, run the script directly and let the script:
1. inspect state
2. optionally repair/restart
3. send a direct Discord alert only when action is needed
4. print `[SILENT]` otherwise

## Procedure

### 1. Confirm the current job is deterministic

Inspect the cron job definition and script.
You are looking for a pattern like:
- script emits JSON such as `running / restarted / failed`
- prompt only says "notify on restart/failure, otherwise nothing"

If that is true, the LLM is not needed.

### 2. Pause the Hermes cron job

Use Hermes CLI so the old job stops firing:

```bash
hermes --profile mycare cron pause <job_id>
hermes --profile mycare cron list --all
```

Verify it shows `[paused]`.

### 3. Rewrite the script to be self-contained

For MyCARE Docker monitor, the script should:
- inspect watched containers with `docker inspect`
- call `docker start <container>` if needed
- build a deterministic message if anything restarted or failed
- send to Discord directly using `DISCORD_BOT_TOKEN` and `DISCORD_MYCARE_CHANNEL_ID`
- print `[SILENT]` and exit 0 when nothing happened

Recommended result contract:
- no event: print `[SILENT]`, exit 0
- restarted and notification succeeded: print JSON summary, exit 0
- failure or notification failure: print JSON summary, exit 1

### 4. Create a systemd user service

Path:
- `~/.config/systemd/user/<name>.service`

Template:

```ini
[Unit]
Description=MyCARE Docker monitor (LLM-free)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=%h/.hermes/profiles/mycare/.env
WorkingDirectory=%h/.hermes/profiles/mycare
ExecStart=/usr/bin/env python3 %h/.hermes/profiles/mycare/scripts/docker_monitor.py
```

Important details:
- use `EnvironmentFile` so Discord token/channel ID are available
- use a profile-local working directory
- oneshot is sufficient for monitors

### 5. Create a systemd user timer

Path:
- `~/.config/systemd/user/<name>.timer`

Template for every 5 minutes:

```ini
[Unit]
Description=Run MyCARE Docker monitor every 5 minutes

[Timer]
OnCalendar=*:0/5
Persistent=true
AccuracySec=30s
Unit=mycare-docker-monitor.service

[Install]
WantedBy=timers.target
```

### 6. Enable and start the timer

```bash
chmod +x ~/.hermes/profiles/mycare/scripts/docker_monitor.py
systemctl --user daemon-reload
systemctl --user enable --now mycare-docker-monitor.timer
```

### 7. Verify end-to-end

Run all of these:

```bash
python3 -m py_compile ~/.hermes/profiles/mycare/scripts/docker_monitor.py
systemctl --user start mycare-docker-monitor.service
systemctl --user status mycare-docker-monitor.service --no-pager --full
systemctl --user status mycare-docker-monitor.timer --no-pager --full
journalctl --user -u mycare-docker-monitor.service -n 20 --no-pager
hermes --profile mycare cron list --all
```

Expected healthy outcome:
- service exits successfully
- journal shows `[SILENT]` when nothing happened
- timer is active and waiting for next run
- old Hermes cron job is paused

## MyCARE Docker monitor reference outcome

The working migration was:
- pause Hermes cron job `a9fc1c8b427a` (`docker_monitor`)
- replace `~/.hermes/profiles/mycare/scripts/docker_monitor.py` with an LLM-free script
- add:
  - `~/.config/systemd/user/mycare-docker-monitor.service`
  - `~/.config/systemd/user/mycare-docker-monitor.timer`
- verify the service prints `[SILENT]` on a healthy run

## Pitfalls

- Do not leave the old Hermes cron active, or you will get duplicate monitoring paths.
- Do not rely on the script printing JSON alone; it must send Discord directly if you want zero LLM involvement.
- Make sure `.env` contains both `DISCORD_BOT_TOKEN` and `DISCORD_MYCARE_CHANNEL_ID`.
- `systemctl status` for a oneshot service often shows `inactive (dead)` after success; that is normal. Check exit status and journal output.
- If you need thread/topic delivery rather than plain channel posting, direct Discord API logic may need expansion.

## Decision rule

If the monitor can be expressed as:
- `if deterministic_event: notify`
- `else: silent`

then prefer this LLM-free timer pattern over Hermes cron.
