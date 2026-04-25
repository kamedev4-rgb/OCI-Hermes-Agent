---
name: hermes-profile-mem0-db-isolation
description: Isolate Hermes mem0 storage per profile using a dedicated PostgreSQL database inside the shared pgvector container.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [hermes, mem0, postgres, profiles, isolation]
---

# Hermes profile mem0 DB isolation

Use when a Hermes profile should keep mem0 memories separate from other profiles while still sharing the same PostgreSQL container.

## Target layout

- One Hermes profile per directory: `~/.hermes/profiles/<profile>/`
- One mem0 database per profile inside the shared PostgreSQL server
- Example:
  - profile `myknot` -> DB `myknot`
  - profile `mycare` -> DB `mycare`
  - hyphens in profile names are converted to underscores for DB names

## Implementation notes

1. Set the profile's `config.yaml` to use `memory.provider: mem0`.
2. Store profile-local mem0 settings in `<profile>/mem0.json`.
3. Put `pg_dbname` in `mem0.json` to the profile-specific DB name.
4. Set `agent_id` in `mem0.json` to the profile name for easier attribution.
5. Create the PostgreSQL database before first real use if it does not exist.
6. Verify mem0 tables appear in that DB (`mem0migrations`, `memories`).
7. Restart the profile's gateway after config changes.

## Current codebase behavior

- `hermes_cli/profiles.py` now seeds a profile-local `mem0.json` from the source/global template and best-effort creates a dedicated PostgreSQL DB during profile creation.
- `plugins/memory/mem0/__init__.py` now defaults `pg_dbname` and `agent_id` from the active profile name when running under `~/.hermes/profiles/<name>/`.
- Profile DB naming rule: replace `-` with `_`.

## Verification

- `hermes --profile <name> memory status`
- `python` with `HERMES_HOME=<profile-dir>` and `load_memory_provider('mem0')`
- `psql` or container SQL to confirm the target DB exists and has mem0 tables
- Restart the gateway and check service health

## Pitfalls

- Profile deletion does not automatically drop the PostgreSQL DB.
- Shared env vars like `MEM0_LLM_BASE_URL` can still affect runtime unless overridden in `mem0.json`.
- Existing memories in the old shared DB are not automatically migrated.
