---
name: daily_check
description: Daily health check workflow for MyKNOT/MyCARE on the Oracle host. Verifies runtime, Discord gateway, database, HTTP surface, and profile/service drift. Use when cron asks for MyCARE 定時診断 / MyKNOT health.
version: 1.0.0
metadata:
  hermes:
    tags: [diagnostics, myknot, mycare, discord, postgres, caddy, hermes]
    related_skills: [systematic-debugging, discord-gateway-profile-drift-diagnosis, hermes-agent]
---

# MyKNOT / MyCARE Daily Check

## Purpose

Run a read-only daily health check for the MyKNOT environment and produce a concise ops report.

Constraints:
- Read-only only unless an approval token explicitly authorizes writes.
- Do not modify `SOUL.md`.
- Do not connect to MyKNOT directly; inspect via PostgreSQL, Docker, systemd, logs, HTTP, and local config.

## When to use

Use this when a cron job or user asks for:
- `MyCARE 定時診断`
- `MyKNOT の健全性確認`
- daily health / maintenance report for MyKNOT or MyCARE

## Core findings this workflow is designed to catch

1. Discord gateway looks healthy even when web serving is broken.
2. `hermes --profile myknot ...` may fail with `Profile 'myknot' does not exist` even while the real gateway is running.
3. The reliable workaround is to inspect the running process and reuse its `HERMES_HOME`, typically:
   - `HERMES_HOME=/home/ubuntu/.hermes/profiles/myknot`
4. Caddy on port 80 may return the default `Caddy works!` page, which means the host is up but MyKNOT is not being served.
5. Legacy/broken systemd units (`hermes-myknot.service`, `hermes-gateway.service`) may remain failed while the real unit is `hermes-gateway-myknot.service`.

## Daily check procedure

Run these checks in order.

### 1) Host baseline

Use terminal:
```bash
uname -a
date -Is
uptime
```

Record time, host, and rough load.

### 2) Container status

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

Expected minimum:
- `myknot_postgres` running
- possibly `portainer`

### 3) Service / process state

Check failed units and relevant services:
```bash
systemctl --failed --no-pager || true
systemctl --user list-units --type=service --all --no-pager 'hermes*'
systemctl --user status hermes-gateway-myknot.service --no-pager || true
systemctl --user status hermes-gateway-mycare.service --no-pager || true
ps -ef | grep -E 'hermes|caddy' | grep -v grep
```

Interpretation:
- `hermes-gateway-myknot.service` active = Discord-side MyKNOT likely alive
- `hermes-myknot.service not-found failed` = stale/broken old unit, report as drift
- if `systemctl --user list-unit-files 'hermes*'` and filesystem checks show no `hermes-myknot.service`, but plain `systemctl status hermes-myknot.service` still shows `Loaded: not-found` + `Active: failed`, treat it as a **system-level failed-state residue**, not an active user unit
- cleanup for that residue is `sudo systemctl reset-failed hermes-myknot.service`; `systemctl --user reset-failed hermes-myknot.service` will fail with `Unit ... not loaded`
- `hermes-gateway.service` may still be the active MyCARE runtime when `HERMES_HOME=/home/ubuntu/.hermes-mycare`; treat this as naming drift, not automatically a failure
- if both `hermes-gateway.service` and `hermes-gateway-mycare.service` are enabled/running (or restarting together), check for Discord token conflict and report MyCARE service duplication/drift
- `hermes-gateway.service failed` without an active replacement = report as drift/problem

### 4) Discover runtime HERMES_HOME

Do this if `hermes --profile myknot ...` fails or if you want grounded runtime state.

Inspect the running MyKNOT PID environment:
```bash
python3 - <<'PY'
import os
pid = <MYKNOT_PID>
with open(f'/proc/{pid}/environ','rb') as f:
    for item in f.read().split(b'\0'):
        if item.startswith(b'HERMES_HOME='):
            print(item.decode())
PY
```

Then use that exact path when calling Hermes CLI:
```bash
HERMES_HOME=/home/ubuntu/.hermes/profiles/myknot hermes status
HERMES_HOME=/home/ubuntu/.hermes/profiles/myknot hermes doctor
```

Important:
- `hermes --profile myknot status` can be false-negative.
- Prefer runtime `HERMES_HOME` over profile-discovery assumptions.

### 5) HTTP surface check

```bash
curl -fsS -o /tmp/myknot_root.out -D - http://127.0.0.1/
head -c 300 /tmp/myknot_root.out
read /etc/caddy/Caddyfile
```

Interpretation:
- `HTTP 200` + body contains `Caddy works!` => web surface is wrong / degraded
- Caddyfile showing only `root * /usr/share/caddy` and `file_server` => default site, not MyKNOT

### 6) Database health

```bash
docker exec myknot_postgres pg_isready -U myknot -d myknot
docker exec myknot_postgres psql -U myknot -d myknot -Atc "select schemaname||'.'||tablename from pg_tables where schemaname='public' order by tablename;"
docker exec myknot_postgres psql -U myknot -d myknot -P pager=off -c "select id,title,severity,status,created_at,closed_at from incidents order by created_at desc limit 10;"
docker exec myknot_postgres psql -U myknot -d myknot -P pager=off -c "select key, value, updated_at from system_state order by updated_at desc limit 20;"
```

Expected tables commonly seen:
- `approval_tokens`
- `incidents`
- `mem0migrations`
- `memories`
- `system_state`

Report:
- whether DB accepts connections
- incident count / recent incidents
- `maintenance_mode`

### 7) Discord log health

Search the MyKNOT logs for current or recent Discord connection state:
```bash
search in /home/ubuntu/.hermes/profiles/myknot/logs for:
- `Connected as`
- `Disconnected`
- `ERROR`
- `Non-retryable`
- today's date
```

High-value signals:
- `Connected as MyKNOT#3032`
- recent inbound and response-ready lines = bot is actually serving traffic
- `Discord bot token already in use` = duplicate gateway conflict
- auth `401` = model/provider auth issue affecting replies

### 8) Cron / config drift check

```bash
HERMES_HOME=/home/ubuntu/.hermes/profiles/myknot hermes cron list || true
```

Also inspect:
- `/home/ubuntu/.hermes/profiles/myknot/config.yaml`
- `/home/ubuntu/.hermes/profiles/mycare/config.yaml`

Useful config fields:
- MyKNOT Discord allowed/home channel
- MyCARE Discord home channel

## Reporting rubric

Use one of these top-level statuses, and report them in bilingual form:
- `HEALTHY（正常）`: Discord runtime, DB, and HTTP surface all correct; no notable drift
- `DEGRADED（一部劣化）`: core bot works, but web surface or config/service drift is broken/misaligned
- `FAILED（障害）`: Discord runtime down, DB unavailable, or no viable service path

For this environment, prefer **format C** for ops reports:
1. natural-language summary of the current state
2. explicit judgment basis: say what you inspected and why it supports the judgment
3. short bullet-style key points at the end

Recommended report structure:
1. timestamp
2. overall status in bilingual form
3. natural-language summary
4. judgment basis (`what was checked` + `what it showed` + `how that maps to the status`)
5. Discord/runtime status
6. database status
7. HTTP/Caddy status
8. service/profile drift
9. priority risks
10. short key-points line

Example key-points line:
- `要点: Discord正常 / DB正常 / Web不整合 / 総合判定 DEGRADED（一部劣化)`

## Current known-good interpretation pattern

If you observe all of the following:
- `hermes-gateway-myknot.service` active
- MyKNOT Discord logs show recent `Connected as` and recent inbound/response activity
- PostgreSQL healthy
- HTTP root returns `Caddy works!`
- stale failed units still exist
- `hermes --profile myknot ...` fails but `HERMES_HOME=... hermes status` works

Then classify as one of these, depending on intended architecture:

### If HTTP/Web is intended to serve MyKNOT
- **DEGRADED**
- Reason:
  - bot runtime is alive
  - database is alive
  - external web surface is misconfigured
  - operational configuration drift remains unresolved

### If MyKNOT is intentionally Discord-first and has no required web UI/API
- Do **not** automatically treat `Caddy works!` as an outage or core degradation.
- Report it as:
  - `HEALTHY（正常）` if Discord runtime + DB are healthy and no other meaningful drift exists, or
  - `DEGRADED（一部劣化）` only if separate real drift remains (for example stale systemd units or actual token conflicts).
- Reason:
  - default Caddy content may simply indicate an unused host-level web service, not a broken MyKNOT surface.
  - judge HTTP findings against intended product topology, not against a generic assumption that every deployment must expose a web UI.

## Restart / drain-timeout interpretation

Be careful when diagnosing an apparent Discord outage immediately after a reload or restart.

Observed pattern:
- logs may show `Gateway drain timed out after 60.0s`
- then `Disconnected`
- the old PID may remain referenced in prior checks
- systemd may later record `status=75/TEMPFAIL`
- because the unit has `Restart=on-failure` and `RestartSec=30`, MyKNOT may auto-restart and reconnect a short time later

Required verification before classifying as FAILED:
1. Re-check `systemctl --user show hermes-gateway-myknot.service -p MainPID,ActiveState,SubState,Result`
2. Confirm the current PID still exists (`ps -p <MainPID>`)
3. Inspect `journalctl --user -u hermes-gateway-myknot.service --since '<recent time>'`
4. Re-read the tail of `agent.log` for a fresh `Connected as MyKNOT#3032`
5. Optionally confirm live socket state for the current PID (`ss -tpn | grep <MainPID>`)

Classification guidance:
- If the service is disconnected and no restart/reconnect has happened after these checks, classify **FAILED**.
- If systemd has already restarted the unit and fresh `Connected as` is present, classify the Discord runtime as recovered and do not report an active outage.
- Distinguish `active (running)` from actual Discord connectivity; require fresh log evidence.

## Pitfalls

- Do not conclude health from `HTTP 200` alone; inspect the body.
- Do not conclude MyKNOT is down just because `hermes --profile myknot` fails.
- Do not rely only on `systemctl --failed`; user-level systemd may still be serving the real gateway.
- Do not write fixes during daily check unless explicitly authorized by approval token.
