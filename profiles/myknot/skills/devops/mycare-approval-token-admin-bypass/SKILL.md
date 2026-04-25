---
name: mycare-approval-token-admin-bypass
description: Implement and verify MyCARE/MyKNOT approval-token controls with requester-bound user IDs, admin bypass, and admin-only token issuance.
---

# When to use
Use when modifying MyCARE approval-token behavior across Hermes profiles, especially to:
- bind tokens to a Discord user ID
- let specific admin Discord user IDs bypass token validation
- restrict token issuance so only admins can create tokens via MyKNOT
- restrict MyCARE Discord interaction to specific user IDs only
- suppress pairing-code responses for unauthorized users
- verify plugin/config rollout across both MyCARE and MyKNOT profiles

# Procedure
1. Confirm profile/plugin locations:
   - MyCARE: `~/.hermes/profiles/mycare/plugins/mycare_approval/`
   - MyKNOT: `~/.hermes/profiles/myknot/plugins/mycare_approval/`
2. Ensure the DB schema includes `approval_tokens.requested_by_user_id`.
3. In the plugin, capture `HERMES_SESSION_USER_ID` when issuing a token and persist it as `requested_by_user_id`.
4. During validation:
   - if current Discord user ID is in `mycare_approval.admin_user_ids`, allow bypass without token
   - otherwise require a valid token whose `requested_by_user_id` matches the current user ID
5. Restrict `/mycare-issue-token` so only configured admin user IDs can issue tokens; return a clear `admin_required` style error for others.
6. Keep `/mycare-validate-token` available for validation checks in both profiles.
7. Add the same `mycare_approval` plugin to both profiles if cross-profile command access is needed.
8. Set the admin Discord user IDs in profile config under `mycare_approval.admin_user_ids` (in this environment, `1490136538972160121` was used).
9. If you need MyCARE to ignore everyone except the admin at the conversation-entry layer, set `DISCORD_ALLOWED_USERS` in `~/.hermes/profiles/mycare/.env` to the admin Discord user ID(s). In this environment it was already set to `1490136538972160121`.
10. To prevent unauthorized DMs from receiving pairing codes, set `unauthorized_dm_behavior: ignore` in `~/.hermes/profiles/mycare/config.yaml` and verify with `load_gateway_config()` that Discord resolves to `ignore`.
11. If MyCARE policy text/SOUL still says all writes require approval tokens, update that wording too so runtime policy and operator instructions do not conflict. In this environment, `~/.hermes/profiles/mycare/SOUL.md` needed to be changed to allow admin-user-ID bypass while keeping non-admin writes token-gated.
12. Verify plugin discovery and run tests for both plugin behavior and CLI/plugin loading.
13. Restart the relevant gateway services and verify with `systemctl --user show ...` plus logs/journal that the new process has loaded the plugin. If foreground restart hangs under the tool wrapper, use a background restart and then confirm `ActiveEnterTimestamp`/`MainPID` changed.

# Verification
- Issue a token as admin via MyKNOT.
- Validate it as the same non-admin requester: should succeed.
- Validate from a different non-admin user: should fail with wrong-user behavior.
- Attempt token issuance as non-admin: should fail.
- Invoke a protected MyCARE action as configured admin without token: should bypass successfully.
- Confirm service restart time/PID changed if a restart was required.

# Pitfalls
- Do not key admin checks off display names or Discord roles unless explicitly required; use immutable Discord user IDs.
- Restarting only one gateway is insufficient if commands are exposed from both MyCARE and MyKNOT profiles.
- A service may still be on the old process even if config files changed; verify `ActiveEnterTimestamp`/PID.
- If memory is unavailable in the environment, rely on a saved skill for future reuse instead of assuming persistence.
