---
name: bitwarden-secret-access
description: "Bitwarden秘密情報取得"
description_full: "Retrieve API keys and other secrets from Bitwarden for kame-dev without exposing values in chat or logs. Covers the required Bitwarden CLI appdata directory, get_secret() behavior, and safe verification steps."
version: 1.0.1
author: MyKNOT
metadata:
  hermes:
    tags: [bitwarden, secrets, bw-cli, api-keys, myknot, hermes]
triggers:
  - "Bitwarden"
  - "ビットウォーデン"
  - "get_secret"
  - "APIキー"
  - "secret"
  - "secrets.py"
---

# Bitwarden Secret Access

## When to use

Use this skill when kame-dev wants to pass API keys, tokens, credentials, webhook URLs, or other secrets to MyKNOT/Hermes safely via Bitwarden.

## Operating rules

- Use Bitwarden Password Manager through `bw` CLI.
- Do **not** use Bitwarden Secrets Manager / `bws`.
- Register Bitwarden items as **Login** items.
- Item name is the service name, e.g. `Discord`, `GitHub`, `OpenAI`, `Gemini`.
- Username field is for client ID, username, or account ID.
- Password field is for API key, password, client secret, or token.
- Use custom fields only when 3+ values are needed.
- Custom field names must be lowercase snake_case, e.g. `app_id`, `public_key`, `token`.
- For Gemini API, kame-dev uses Bitwarden item name `Gemini API` (not `Gemini`); store the API key in the password field and retrieve with `get_secret("Gemini API")`.

## Known setup

- Bitwarden CLI exists at:

```bash
/usr/local/bin/bw
```

- Verified CLI version during setup:

```text
2026.4.1
```

- Shared helper module:

```text
/home/ubuntu/.hermes/skills/common/secrets.py
```

- Import path:

```python
import sys
sys.path.insert(0, "/home/ubuntu/.hermes/skills")
from common.secrets import get_secret, create_secret, update_secret, clear_cache
```

- `get_secret(item_name, field="password")` unlocks Bitwarden automatically using `BW_PASSWORD` and returns the requested field.
- `field` supports `password`, `username`, `notes`, or a custom field name.

## Critical environment detail

In MyKNOT/Hermes profile sessions, the default Bitwarden CLI data directory can point at the profile-local home:

```text
/home/ubuntu/.hermes/profiles/myknot/home/.config/Bitwarden CLI
```

That directory may be unauthenticated and causes:

```text
bw unlock failed: You are not logged in.
```

The logged-in Bitwarden CLI data directory observed on this machine is:

```text
/home/ubuntu/.config/Bitwarden CLI
```

Therefore, set this environment variable when calling `get_secret()` unless the profile environment has already been fixed globally:

```bash
export BITWARDENCLI_APPDATA_DIR="/home/ubuntu/.config/Bitwarden CLI"
```

## Safe verification

Never print real secrets. To verify unlock without exposing data, call `get_secret()` for a deliberately nonexistent item. Success looks like `Not found` after unlock, not `not logged in`.

```bash
BITWARDENCLI_APPDATA_DIR="/home/ubuntu/.config/Bitwarden CLI" python - <<'PY'
import sys
sys.path.insert(0, "/home/ubuntu/.hermes/skills")
from common.secrets import get_secret
try:
    get_secret("__MYKNOT_NON_EXISTENT_TEST_ITEM__")
except Exception as e:
    print(type(e).__name__ + ": " + str(e)[:200])
PY
```

Expected safe result:

```text
RuntimeError: bw get item '__MYKNOT_NON_EXISTENT_TEST_ITEM__' failed: Not found.
```

If it says `bw unlock failed: You are not logged in`, the Bitwarden appdata directory is wrong or the CLI is not logged in.

## Retrieve a secret safely

Use Python and do not print the secret. Pass it directly into environment variables, config files with restricted permissions, or API clients.

```python
import sys
sys.path.insert(0, "/home/ubuntu/.hermes/skills")
from common.secrets import get_secret

api_key = get_secret("OpenAI")  # default field: password
client_id = get_secret("Discord", field="username")
client_secret = get_secret("Discord", field="password")
app_id = get_secret("Discord", field="app_id")  # custom field
```

## Shell pattern for tools/commands

```bash
BITWARDENCLI_APPDATA_DIR="/home/ubuntu/.config/Bitwarden CLI" python - <<'PY'
import sys, os, subprocess
sys.path.insert(0, "/home/ubuntu/.hermes/skills")
from common.secrets import get_secret

key = get_secret("SomeService")
env = {**os.environ, "SOME_SERVICE_API_KEY": key}
# Run command without printing key
subprocess.run(["some-command", "--safe-arg"], env=env, check=True)
PY
```

## Create/update entries

Use helper functions instead of manually constructing `bw` commands when possible:

```python
create_secret("NewService", password="apikey123")
update_secret("ExistingService", password="new-secret")
update_secret("Discord", custom_fields={"webhook_url": "https://..."})
```

Do not ask the user to paste secrets into Discord/chat. Prefer that the user adds/updates the item in Bitwarden, then provide only the item name and field name.

## Pitfalls

- Do not run `bw get password ...` directly in a way that prints values to stdout.
- Do not include secrets in final answers, command output, logs, screenshots, or shared-notes.
- `BW_PASSWORD` must be present for auto-unlock. If missing, `secrets.py` raises `BW_PASSWORD is not set in the environment`.
- `BW_SESSION` is not required for `get_secret()` because `secrets.py` calls `bw unlock --passwordenv BW_PASSWORD --raw` and caches the session per process.
- If Bitwarden password changes or vault locks unexpectedly, call `clear_cache()` in Python or restart the process.
