---
name: mycare-admin-bypass-approval-audit
description: Audit whether MyCARE admin bypass is actually implemented and explain why a gateway still asks for an approval token or /approve.
version: 1.0.0
metadata:
  hermes:
    tags: [mycare, approval, admin-bypass, gateway, discord, postgres]
---

# MyCARE admin-bypass approval audit

## When to use
Use when a user says one of these:
- "承認トークンはもう不要なはず"
- "MyCARE の実装状況を確認して"
- "なぜ管理者なのに承認トークンを要求されるのか"
- "自然文の『承認します』で通るようにしたい"

## Goal
Separate these two concerns:
1. **MyCARE approval implementation** — whether admin bypass and user-bound approval tokens exist.
2. **Gateway dangerous-command approval flow** — whether the running gateway accepts only `/approve` and `/deny`, or also accepts natural-language approval text.

Do not assume they are the same system.

## Audit procedure

### 1. Confirm MyCARE profile config
Read:
- `/home/ubuntu/.hermes/profiles/mycare/config.yaml`

Check for:
- `mycare_approval.admin_user_ids`
- `mycare_approval.allow_admin_bypass: true`

If present, note that the profile is configured for admin bypass.

### 2. Confirm plugin exists and what it does
Read:
- `/home/ubuntu/.hermes/profiles/mycare/plugins/mycare_approval/plugin.yaml`
- `/home/ubuntu/.hermes/profiles/mycare/plugins/mycare_approval/__init__.py`

High-value lines to verify:
- `_get_session_user_id()` reads `HERMES_SESSION_USER_ID`
- `_get_admin_user_ids()` loads config/env admin IDs
- `issue_token()` rejects non-admins with `reason: "admin_required"`
- `validate_token("")` returns `ok: True`, `reason: "admin_bypass"` for admin users when bypass is enabled
- token rows are bound via `requested_by_user_id`

### 3. Confirm tests cover the behavior
Read or search:
- `tests/plugins/test_mycare_approval_plugin.py`

Expected evidence:
- admin without token gets `admin_bypass`
- non-admin cannot issue token
- token validation rejects wrong user ID
- token issuance binds `requested_by_user_id`

### 4. Confirm the running MyCARE service uses the correct profile
Run:
```bash
systemctl --user show hermes-gateway-mycare.service -p MainPID,ActiveState,SubState,Environment
```

Expected evidence:
- `ActiveState=active`
- `SubState=running`
- `HERMES_HOME=/home/ubuntu/.hermes/profiles/mycare`

This matters because config/plugin checks are meaningless if the runtime points somewhere else.

### 5. Check current DB state separately from implementation
Run:
```bash
docker exec myknot_postgres psql -U myknot -d myknot -P pager=off -c "select count(*) as total, count(requested_by_user_id) as bound_count, count(*) filter (where requested_by_user_id is null) as unbound_count from approval_tokens;"
```

Interpretation:
- `unbound_count > 0` can simply mean legacy tokens still exist
- this does **not** disprove the current plugin implementation
- report it as legacy DB residue, not necessarily a current logic failure

### 6. Check gateway approval behavior separately
Read:
- `gateway/run.py`
- `tools/approval.py`
- optionally `tests/gateway/test_approve_deny_commands.py`

Key findings to look for:
- `gateway/run.py` handles dangerous command approval via `_handle_approve_command()` and `_handle_deny_command()`
- comments explicitly say pending exec approvals are handled by `/approve` and `/deny`
- there is intentionally **no bare-text matching** for normal conversation text like `yes` or `承認します`
- `tools/approval.py` returns `status="approval_required"` and waits for gateway approval resolution

## Critical interpretation pattern
If all of these are true:
- MyCARE config has `admin_user_ids` and `allow_admin_bypass: true`
- the plugin implements `admin_bypass`
- plugin tests cover that behavior
- the running service uses the MyCARE profile
- gateway code still requires `/approve` and `/deny`

Then the correct conclusion is:
- **MyCARE admin bypass is implemented**
- **gateway natural-language approval is a separate unresolved behavior**
- the mismatch is not "MyCARE lacks admin bypass"; it is "gateway dangerous-command approval does not consult that bypass for plain-text replies"

## Recommended report wording
Use concise language like:
- "MyCARE 実装上は管理者 bypass は入っています。"
- "一方で gateway 側は危険コマンド承認を `/approve` `/deny` に限定しています。"
- "したがって、現在のズレは MyCARE 未実装ではなく、gateway の自然文承認未対応です。"

## If asked what to implement next
Point to:
- `gateway/run.py`
- approval handling around `_handle_approve_command()` / `_handle_deny_command()`
- tests in `tests/gateway/test_approve_deny_commands.py`

Suggested behavior:
- only when a dangerous-command approval is actually pending
- only for configured admin users
- only for strong approval phrases (not generic `yes`)
- map the message to the same path as `/approve`

## Pitfalls
- Do not treat a legacy expired/unbound token row as proof the new plugin is broken.
- Do not assume MyCARE admin bypass automatically changes gateway dangerous-command approval behavior.
- Do not say "token is unnecessary everywhere" unless you verified both plugin behavior and gateway approval flow.
