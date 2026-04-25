---
name: mycare-mem0-enablement
description: Enable mem0-only memory for the MyCARE Hermes profile, including the profile-local override needed when global mem0 settings or env vars would otherwise break MyCARE.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [mycare, hermes, mem0, memory, profiles, gateway]
---

# MyCARE mem0 enablement

Use when the user wants MyCARE to use mem0 for past-content lookup, especially when built-in curated memory is not wanted.

## When this skill applies
- The target profile is `mycare`
- The user wants past content to be searchable/retrievable during incidents
- Built-in `MEMORY.md` / `USER.md` prompt injection is unnecessary or undesirable
- `memory status` may say mem0 is available, but actual mem0 tool calls fail because MyCARE is inheriting bad global mem0 settings or env vars

## Key finding
For Hermes, built-in memory flags and external memory provider selection are separate:
- `memory.memory_enabled` and `memory.user_profile_enabled` control built-in prompt-injected memory
- `memory.provider` controls the external provider plugin

So **mem0-only** operation is valid and should use:

```yaml
memory:
  memory_enabled: false
  user_profile_enabled: false
  provider: mem0
```

## Important pitfall
`hermes memory status` can report:
- `Provider: mem0`
- `Status: available`

while real Mem0 behavior is still misconfigured.

Two distinct failure modes were observed in this environment:

1. **Wrong global config / missing effective API key**
   - MyCARE initially inherited global mem0 settings/env that resolved to:
     - `llm_provider: openai`
     - NVIDIA-style base URL
     - missing/incorrect effective API key path for actual mem0 tool usage
   - This produced runtime errors like:
     - `{"error": "OPENAI_API_KEY not set."}`

2. **Profile `.env` overriding `mem0.json`**
   - `_load_config()` loads `MEM0_*` from env first, then overlays non-empty keys from `mem0.json`.
   - If `mem0.json` sets `llm_provider: openai-codex` and `llm_model: gpt-4.1` **but does not set `llm_base_url`**, a profile `.env` containing
     - `MEM0_LLM_BASE_URL=https://integrate.api.nvidia.com/v1`
     can still leak through.
   - Because `_resolve_llm_config()` for `openai-codex` uses `base_url_override or creds["base_url"]`, MyCARE can end up trying to call **NVIDIA NIM with `gpt-4.1` + Codex OAuth credentials**, which fails (observed as `404 page not found`).

The initial fix was to create a **profile-local**:
- `/home/ubuntu/.hermes/profiles/mycare/mem0.json`

but that alone is not sufficient if conflicting `MEM0_*` vars remain in the profile `.env`.

## Procedure

### 1. Inspect current MyCARE memory config
Check:
- `/home/ubuntu/.hermes/profiles/mycare/config.yaml`
- `systemctl --user status hermes-gateway-mycare.service --no-pager --full`
- `hermes --profile mycare memory status`

Verify whether MyCARE currently has something like:

```yaml
memory:
  memory_enabled: false
  user_profile_enabled: false
  provider: builtin
```

### 2. Confirm mem0 plugin availability
Use Python or Hermes CLI to verify mem0 actually loads under the MyCARE profile.

Example:

```bash
cd /home/ubuntu/.hermes/hermes-agent
/home/ubuntu/.hermes/hermes-agent/venv/bin/python - <<'PY'
import os
os.environ['HERMES_HOME']='/home/ubuntu/.hermes/profiles/mycare'
from plugins.memory import load_memory_provider
p = load_memory_provider('mem0')
print('provider_loaded=', bool(p))
print('provider_name=', getattr(p,'name',None))
print('is_available=', p.is_available() if p else None)
PY
```

Expected:
- provider loads
- name is `mem0`
- `is_available=True`

### 3. Switch MyCARE config to mem0-only
Edit `/home/ubuntu/.hermes/profiles/mycare/config.yaml`:

```yaml
memory:
  memory_enabled: false
  user_profile_enabled: false
  memory_char_limit: 2200
  user_char_limit: 1375
  provider: mem0
  nudge_interval: 10
  flush_min_turns: 6
```

### 4. Check whether global mem0 config is unsuitable
Inspect:
- `/home/ubuntu/.hermes/mem0.json`
- effective `_load_config()` for MyCARE
- relevant env vars like `MEM0_LLM_PROVIDER`, `MEM0_LLM_BASE_URL`, `OPENAI_API_KEY`

If direct mem0 calls under MyCARE return errors such as `OPENAI_API_KEY not set`, do **not** assume memory is working just because `memory status` says mem0 is available.

### 5. Create a profile-local MyCARE mem0 override
Write:
- `/home/ubuntu/.hermes/profiles/mycare/mem0.json`

Known-good example for this environment (current working config):

```json
{
  "pg_host": "localhost",
  "pg_port": 5432,
  "pg_user": "myknot",
  "pg_password": "jG0LJjpyVv",
  "pg_dbname": "mycare",
  "llm_provider": "openai",
  "llm_model": "meta/llama-3.3-70b-instruct",
  "llm_base_url": "https://integrate.api.nvidia.com/v1",
  "user_id": "hermes-user",
  "agent_id": "mycare"
}
```

This intentionally pins MyCARE Mem0 to the same working NVIDIA NIM path as MyKNOT while keeping the database isolated per profile.

### 6. Verify with real mem0 tool calls
Do not stop at `memory status`. Run real mem0 operations.

Example:

```bash
cd /home/ubuntu/.hermes/hermes-agent
/home/ubuntu/.hermes/hermes-agent/venv/bin/python - <<'PY'
import os
os.environ['HERMES_HOME']='/home/ubuntu/.hermes/profiles/mycare'
from plugins.memory import load_memory_provider
p = load_memory_provider('mem0')
p.initialize(session_id='mycare-verification', user_id='1490136538972160121')
print(p.handle_tool_call('mem0_search', {'query':'approval token', 'top_k': 2}))
print(p.handle_tool_call('mem0_profile', {}))
PY
```

Success criteria:
- returns JSON results, not an auth/config error
- `mem0_profile` returns a count
- `mem0_search` returns matching memories

### 7. Restart and re-check gateway
After config changes:

```bash
systemctl --user restart hermes-gateway-mycare.service
systemctl --user status hermes-gateway-mycare.service --no-pager --full
journalctl --user -u hermes-gateway-mycare.service --since '5 minutes ago' --no-pager | tail -80
```

## Verification checklist
- [ ] MyCARE config has `provider: mem0`
- [ ] built-in memory remains disabled if mem0-only is desired
- [ ] `/home/ubuntu/.hermes/profiles/mycare/mem0.json` exists when needed
- [ ] `hermes --profile mycare memory status` shows mem0 active
- [ ] direct `mem0_search` works under `HERMES_HOME=/home/ubuntu/.hermes/profiles/mycare`
- [ ] gateway restarts cleanly and remains running

## Notes
- `provider: builtin` is not the right way to express built-in-only external memory; built-in behavior is controlled by the two boolean flags, while provider plugins are loaded by name.
- In this environment, the decisive fix was **profile-local mem0.json**, not merely flipping `provider` to `mem0`.
- If the user wants incident retrospection and past-content lookup, mem0 is a better fit than built-in prompt memory.
