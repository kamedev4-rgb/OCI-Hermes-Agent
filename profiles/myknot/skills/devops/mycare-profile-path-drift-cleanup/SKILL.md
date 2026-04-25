---
name: mycare-profile-path-drift-cleanup
description: Audit and clean up MyCARE path drift after migration from ~/.hermes-mycare to ~/.hermes/profiles/mycare, distinguishing live references from historical residue and safely archiving the residual old home.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [mycare, hermes, profiles, migration, drift, cleanup, systemd]
---

# MyCARE profile path drift cleanup

Use when MyCARE has been migrated from the old standalone home `~/.hermes-mycare` to the profile-based home `~/.hermes/profiles/mycare`, and you need to verify or fix leftover path references.

## Goal

Separate **live configuration drift** from **historical residue**, then fix only the live references and archive the residual old home safely.

## Proven findings in this environment

- The live MyCARE gateway runs via systemd user service with:
  - `--profile mycare`
  - `HERMES_HOME=/home/ubuntu/.hermes/profiles/mycare`
- A common missed live reference is:
  - `~/.hermes/profiles/mycare/config.yaml`
  - `quick_commands.soul.command: /bin/cat /home/ubuntu/.hermes-mycare/SOUL.md`
- The old residual home may still exist at `/home/ubuntu/.hermes-mycare` even after migration.
- Old references inside `sessions/`, `cron/output/`, backups, and request dumps are usually historical only and should **not** be treated as active drift.
- In this environment, no process was actively using `/home/ubuntu/.hermes-mycare` before archival (`lsof +D` returned nothing).

## Audit sequence

### 1. Confirm live runtime first
Check systemd and process args before editing anything.

Commands:

```bash
systemctl --user status hermes-gateway-mycare.service --no-pager -l | sed -n '1,40p'
ps -ef | grep -E 'hermes_cli.main --profile mycare gateway run' | grep -v grep
```

What to verify:
- service is active
- invocation includes `--profile mycare`
- service unit or environment points to `/home/ubuntu/.hermes/profiles/mycare`

### 2. Search for old-path references broadly
Use content search to find `/.hermes-mycare` references.

Recommended searches:

```bash
search in /home/ubuntu/.hermes/profiles/mycare
search in /home/ubuntu/.config/systemd/user
search in /home/ubuntu/.hermes/hermes-agent
search in /home/ubuntu for broad residue if needed
```

Interpretation rule:
- `config.yaml`, systemd unit files, scripts, plugin configs = potentially live
- `sessions/`, `cron/output/`, backups, request dumps = historical unless executed directly

### 3. Inspect the MyCARE config around quick commands
Read the `quick_commands` block directly.

Expected bad pattern:

```yaml
quick_commands:
  soul:
    type: exec
    command: /bin/cat /home/ubuntu/.hermes-mycare/SOUL.md
```

### 4. Fix the live config reference
Replace the old SOUL path with the profile-local path:

```yaml
quick_commands:
  soul:
    type: exec
    command: /bin/cat /home/ubuntu/.hermes/profiles/mycare/SOUL.md
```

### 5. Check whether the old residual home is still in use
Before moving or deleting the old directory, verify no live process has it open.

Command:

```bash
lsof +D /home/ubuntu/.hermes-mycare 2>/dev/null || true
```

If empty, it is safe to archive.

### 6. Archive the residual old home instead of deleting it
Do **not** hard-delete immediately. Move it into legacy storage with a timestamp.

Example:

```bash
stamp=$(date +%Y%m%d_%H%M%S)
mv /home/ubuntu/.hermes-mycare \
  /home/ubuntu/.hermes/legacy-homes/mycare_residual_${stamp}
```

This preserves:
- old logs
- old sessions
- old cron state
- the previous SOUL file

### 7. Restart and verify
Restart MyCARE after live config changes.

```bash
systemctl --user restart hermes-gateway-mycare.service
systemctl --user status hermes-gateway-mycare.service --no-pager -l | sed -n '1,40p'
journalctl --user -u hermes-gateway-mycare.service --since '2 minutes ago' --no-pager | tail -n 40
```

Success criteria:
- service returns to `active (running)`
- `/home/ubuntu/.hermes-mycare` no longer exists
- config points to `/home/ubuntu/.hermes/profiles/mycare/SOUL.md`
- remaining `/.hermes-mycare` hits are only historical residue

## What counts as okay residue
These can remain after cleanup:
- `~/.hermes/profiles/mycare/sessions/...`
- `~/.hermes/profiles/mycare/cron/output/...`
- `~/.hermes/refactor_backups/...`
- request dumps and archived transcripts

Reason: they are historical records, not live runtime configuration.

## Pitfalls

1. **Do not confuse archived text with active config.**
   A global search will find many stale mentions in logs and transcripts.

2. **Do not delete the old home before checking live usage.**
   Use `lsof +D` first.

3. **Do not assume systemd units are wrong just because historical outputs mention the old home.**
   Read the actual loaded unit files under `~/.config/systemd/user/`.

4. **Restart after changing live config.**
   Config edits alone are not enough for the running gateway.

## Expected final report shape

- live MyCARE runtime confirmed on profile-based home
- `quick_commands.soul` fixed to profile-local SOUL path
- residual `/home/ubuntu/.hermes-mycare` archived under `~/.hermes/legacy-homes/...`
- only historical `/.hermes-mycare` references remain in logs/transcripts/backups
