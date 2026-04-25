---
name: hermes-profile-memory-audit
description: Audit whether a Hermes profile is actually using built-in memory or an external memory provider such as mem0, separating active config from leftover database state.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [hermes, memory, profiles, mem0, debugging, audit]
    related_skills: [hermes-agent, systematic-debugging]
---

# Hermes Profile Memory Audit

Use this when a user asks whether a Hermes profile has memory enabled, wants to enable memory, or when global memory settings may differ from profile-specific settings.

## Goal

Determine the actual current state for one profile:
1. Is the profile process running?
2. What does the profile config say?
3. Is built-in prompt memory enabled?
4. Is an external provider such as mem0 configured?
5. Are database tables or old data merely present without the profile actually using them?

## Why this skill exists

These points are easy to misread:
- global config may show mem0 enabled while a profile overrides it
- a database can contain `memories` or `mem0migrations` tables even when the target profile is not using mem0 now
- `hermes --profile <profile> memory status` helps, but it does not replace checking the profile config flags
- an empty profile `memories/` directory proves only that the path exists, not active usage

## Recommended audit sequence

### 1) Confirm live profile/service context
Check the running gateway or process and verify which profile/home it is using.

Collect:
- whether the service is running
- exact profile used in the process invocation
- effective Hermes home
- whether an env file is being loaded

### 2) Read the profile config directly
Do not rely only on global config.

Inspect the profile `config.yaml`, especially the `memory:` block.

Key fields:
- `memory_enabled`
- `user_profile_enabled`
- `provider`
- `memory_char_limit`
- `user_char_limit`

Interpretation:
- `memory_enabled: false` and `user_profile_enabled: false` means built-in prompt memory is off
- `provider: builtin` means no external memory plugin is selected
- `provider: mem0` means external mem0 should be investigated further

### 3) Compare with global defaults
Read the main Hermes config too.

Purpose:
- determine whether the target profile is inheriting defaults or overriding them
- explicitly call out cases like “global mem0 is on, but this profile disables memory”

### 4) Check profile-local memory artifacts
Inspect the profile home for:
- `memories/`
- `mem0.json`
- `.env`

Useful checks:
- Does `memories/` exist, and is it empty?
- Does `mem0.json` exist?
- Does `.env` contain mem0 or LLM-related keys?

Relevant env keys to check for presence only:
- `MEM0_PG_HOST`
- `MEM0_PG_PORT`
- `MEM0_PG_USER`
- `MEM0_PG_PASSWORD`
- `MEM0_PG_DBNAME`
- `MEM0_LLM_PROVIDER`
- `MEM0_LLM_MODEL`
- `MEM0_LLM_BASE_URL`
- provider auth keys

Important: report whether keys are present and non-empty, but never echo secret values.

### 5) Use Hermes memory CLI carefully
Run the profile memory status command.

Interpretation rules:
- `Provider: builtin` means no external provider is active
- for builtin, plugin-install messages are not the same thing as built-in prompt memory being off
- this command does not replace checking `memory_enabled` and `user_profile_enabled` in config

### 6) If mem0 is suspected, inspect provider requirements
Check the mem0 plugin code or docs.

Important learned behavior:
- mem0 may fall back to general Postgres env vars rather than requiring every explicit `MEM0_*` variable
- missing explicit mem0 variables does not always mean the plugin cannot initialize
- however, if the profile config says builtin or the memory flags are off, mem0 is still not the active path for that profile

### 7) Treat database tables as supporting evidence only
You may inspect database tables such as:
- `memories`
- `mem0migrations`

Do not conclude “the profile is using mem0” just because those tables exist or contain rows.

Use DB checks only to say things like:
- the shared database contains prior memory data
- memory-related tables exist on the host
- this does or does not align with the profile’s active configuration

## Reporting order

Summarize in this order:
1. service or process state
2. profile config state
3. difference from global config
4. local artifacts present or missing
5. external provider status
6. DB observations, clearly labeled as non-authoritative for active profile usage
7. bottom-line conclusion: active, disabled, or not fully configured

## Example conclusion language

- “The profile gateway is running, but profile config has memory flags off, so memory is effectively disabled.”
- “Global Hermes config uses mem0, but this profile overrides that and stays on builtin or disabled settings.”
- “The database has memory tables and rows, but that only proves the host has memory data; it does not prove this profile is currently using mem0.”

## Pitfalls

- Do not confuse global config with profile config.
- Do not equate DB residue with active profile usage.
- Do not assume missing explicit mem0 env vars alone proves mem0 cannot work; check provider fallback behavior.
- Do not use the memory status command as the only source of truth.
