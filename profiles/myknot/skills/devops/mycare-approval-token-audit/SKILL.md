---
name: mycare-approval-token-audit
description: Audit whether MyCARE approval tokens are actually bound to a messaging-platform user ID, by tracing user identity through Hermes gateway code and checking the backing PostgreSQL schema.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [mycare, hermes, approval, discord, postgres, audit]
---

# MyCARE approval token user-ID binding audit

Use this when asked questions like:
- "Can MyCARE judge approval tokens by user ID?"
- "Is the approval token tied to the Discord user who requested it?"
- "Does Hermes/MyCARE already store requester identity for approvals?"

## Goal

Answer three separate questions, in order:

1. Does the platform adapter capture the sender's user ID?
2. Does gateway/session auth preserve and use that user ID?
3. Does the MyCARE approval-token persistence layer store a requester user ID for comparison at approval time?

Do **not** assume these are the same thing.

## Steps

### 1. Check MyCARE profile constraints first

Read:
- `~/.hermes/profiles/mycare/SOUL.md`
- `~/.hermes/profiles/mycare/config.yaml`

Important reminder: MyCARE may forbid writes without an approval token, so start with read-only inspection.

### 2. Trace user identity from Discord into Hermes source

Inspect Discord adapter and gateway auth flow.

Key files:
- `~/.hermes/hermes-agent/gateway/platforms/discord.py`
- `~/.hermes/hermes-agent/gateway/run.py`
- optionally `~/.hermes/hermes-agent/gateway/session.py`

What to verify:
- Discord inbound messages map `message.author.id` or `interaction.user.id` into `source.user_id`
- gateway auth logic uses `source.user_id`
- any button/approval UI is authorized by allowed-user lists, not necessarily by original requester

Useful searches:
- `message.author.id`
- `interaction.user.id`
- `user_id=`
- `_is_user_authorized`
- `send_exec_approval`
- `ExecApprovalView`

### 3. Check whether Hermes dangerous-command approval is requester-bound

Inspect:
- `~/.hermes/hermes-agent/tools/approval.py`
- Discord approval UI sections in `gateway/platforms/discord.py`

Important finding to remember:
- Hermes gateway approvals can be authorized by configured allowed users, and are **not automatically bound to the original requester** unless code explicitly stores and compares requester identity.

### 4. Inspect MyCARE approval token storage

Find the actual backing schema instead of guessing from code comments.

In this environment, the MyKNOT/MyCARE PostgreSQL service is exposed via Docker Compose at:
- `/home/ubuntu/myknot/docker-compose.yml`
- container name: `myknot_postgres`

If `psql` is missing on the host, use Docker:

```bash
docker exec myknot_postgres psql -U myknot -d myknot -c "\d+ approval_tokens"
docker exec myknot_postgres psql -U myknot -d myknot -c "select count(*) from approval_tokens;"
docker exec myknot_postgres psql -U myknot -d myknot -c "select * from approval_tokens limit 5;"
```

### 5. Interpret the result carefully

If `approval_tokens` has columns like:
- `token`
- `incident_id`
- `action`
- `params`
- `status`
- `created_at`
- `expires_at`

but **no** `requested_by_user_id` / `user_id` / equivalent requester field, then conclude:

- platform user IDs are available,
- Hermes gateway auth uses user IDs,
- but MyCARE approval tokens are **not yet user-ID-bound in persistence**.

That means "possible with small changes" is correct, but "already implemented" is not.

## Recommended implementation options

### Preferred
Add a dedicated column such as:
- `requested_by_user_id text`

Then:
1. store requester Discord user ID when issuing the token,
2. compare it against current `source.user_id` when redeeming/using the token,
3. reject mismatches.

### Minimal but weaker
Store requester ID inside `params` JSONB and compare there.

This works, but is worse for:
- auditing,
- indexing/querying,
- future migrations,
- clarity.

## Proven implementation pattern in this environment

This is now implemented for MyCARE via a **profile-local plugin** instead of patching Hermes core.

### Files
- `~/.hermes/profiles/mycare/plugins/mycare_approval/plugin.yaml`
- `~/.hermes/profiles/mycare/plugins/mycare_approval/__init__.py`

### What the plugin does
- reads the current gateway user from `gateway.session_context.get_session_env("HERMES_SESSION_USER_ID")`
- issues tokens into PostgreSQL with `requested_by_user_id`
- validates tokens only when the current session user ID matches the stored requester ID
- registers:
  - tool: `mycare_approval_token`
  - slash commands:
    - `/mycare-issue-token`
    - `/mycare-validate-token`

### Database migration strategy
Use lazy schema enforcement inside the plugin repository layer:

```sql
ALTER TABLE approval_tokens ADD COLUMN IF NOT EXISTS requested_by_user_id text;
CREATE INDEX IF NOT EXISTS approval_tokens_requested_by_user_id_idx
ON approval_tokens (requested_by_user_id);
UPDATE approval_tokens
SET requested_by_user_id = COALESCE(requested_by_user_id, params->>'requested_by_user_id')
WHERE requested_by_user_id IS NULL
  AND params IS NOT NULL
  AND params ? 'requested_by_user_id';
```

This avoids needing a separate migration framework for the current MyCARE setup.

### Validation behavior to enforce
Reject in these cases:
- missing current session user ID
- invalid token format (non-UUID)
- token not found
- token exists but has no bound requester ID
- requester ID differs from current session user ID (`wrong_user`)
- token status is not approved
- token expired

### Verification steps that worked
1. add tests for issue + validate behavior before implementation
2. run targeted tests:
   - `pytest tests/plugins/test_mycare_approval_plugin.py -q`
3. run related plugin tests:
   - `pytest tests/hermes_cli/test_plugins.py tests/plugins/test_mycare_approval_plugin.py -q`
4. verify plugin discovery with:
   - `HERMES_HOME=/home/ubuntu/.hermes/profiles/mycare python ... PluginManager().discover_and_load()`
5. verify DB column exists:
   - `docker exec myknot_postgres psql -U myknot -d myknot -c "select column_name, data_type from information_schema.columns where table_name = 'approval_tokens' and column_name = 'requested_by_user_id';"`
6. do an end-to-end check by issuing a token for one user ID and confirming:
   - same user validates successfully
   - different user gets `wrong_user`
7. restart MyCARE gateway after adding the plugin:
   - `systemctl --user restart hermes-gateway-mycare.service`

## Pitfalls

1. **Do not confuse allowlist auth with requester binding.**
   A button that only allowed users can click is not the same as "only the original requester can approve".

2. **Do not stop at gateway code.**
   You must also inspect the backing DB schema, or you'll overclaim.

3. **Host `psql` may be unavailable.**
   In this environment, use `docker exec myknot_postgres psql ...` instead.

4. **`params` may contain labels or scope text but still no user ID.**
   Check actual sample rows before concluding.

## Expected answer shape

Give the user a short answer in this structure:
- Yes, it is implementable.
- No, current persistence does not appear to bind approval tokens to user ID.
- Discord/Hermes already capture `source.user_id`, so the missing piece is storing and comparing requester identity in MyCARE approval tokens.
- Recommend dedicated DB column over JSONB if they want a robust implementation.
