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

Use one of these top-level statuses:
- `HEALTHY`: Discord runtime, DB, and HTTP surface all correct; no notable drift
- `DEGRADED`: core bot works, but web surface or config/service drift is broken/misaligned
- `FAILED`: Discord runtime down, DB unavailable, or no viable service path

Recommended report structure:
1. timestamp
2. overall status
3. Discord/runtime status
4. database status
5. HTTP/Caddy status
6. service/profile drift
7. priority risks

## Current known-good interpretation pattern

If you observe all of the following:
- `hermes-gateway-myknot.service` active
- MyKNOT Discord logs show recent `Connected as` and recent inbound/response activity
- PostgreSQL healthy
- HTTP root returns `Caddy works!`
- stale failed units still exist
- `hermes --profile myknot ...` fails but `HERMES_HOME=... hermes status` works

Then classify as:
- **DEGRADED**

Reason:
- bot runtime is alive
- database is alive
- external web surface is misconfigured
- operational configuration drift remains unresolved

## Pitfalls

- Do not conclude health from `HTTP 200` alone; inspect the body.
- Do not conclude MyKNOT is down just because `hermes --profile myknot` fails.
- Do not rely only on `systemctl --failed`; user-level systemd may still be serving the real gateway.
- Do not write fixes during daily check unless explicitly authorized by approval token.
