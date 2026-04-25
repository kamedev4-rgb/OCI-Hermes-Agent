---
name: codex-quota-monitoring
description: Investigate whether Codex 5-hour and weekly quota data can be fetched directly, and choose between direct API polling and local rolling-window accumulation for notifications.
version: 1.0.0
metadata:
  hermes:
    tags: [codex, quota, monitoring, discord, openai-codex, usage]
---

# Codex quota monitoring

Use when the user wants notifications for Codex usage windows such as:
- 5-hour usage percent or remaining quota
- 5-hour reset time
- weekly usage percent or remaining quota
- weekly reset time

## Core lesson

Do not assume standard OpenAI Usage API or `x-ratelimit-*` headers solve this.
For Hermes setups using provider `openai-codex`, the traffic may actually go to:

- `https://chatgpt.com/backend-api/codex/responses`

That can mean the user is asking about product-side Codex quotas rather than normal API RPM/TPM limits.

## Investigation procedure

### 1. Confirm what backend Hermes is actually using

Search Hermes code and request dumps first.

Useful searches:

```bash
search_files pattern="backend-api/codex" path="/home/ubuntu/.hermes/hermes-agent" target="content"
search_files pattern="backend-api/codex/responses" path="/home/ubuntu/.hermes" target="content" file_glob="*.json"
```

What to look for:
- `hermes_cli/auth.py` default Codex base URL
- `hermes_cli/providers.py` overlay using `https://chatgpt.com/backend-api/codex`
- request dump JSON files showing real outbound URLs

### 2. Do not equate rate-limit headers with 5h / weekly quotas

`x-ratelimit-limit-*`, `x-ratelimit-remaining-*`, and reset headers are typically short-horizon API throttling signals.
They are not evidence that 5-hour or weekly product quotas are available.

### 3. Check whether a direct quota endpoint exists

Before designing notifications, inspect:
- Hermes code for any Codex-specific usage/limits endpoint
- captured request dumps for quota-related fields
- response metadata or headers if you have authenticated access

Search patterns:
- `usage`
- `quota`
- `remaining`
- `reset`
- `weekly`
- `5h`
- `subscription`

If no clear endpoint or response field is found, do not claim direct retrieval is available.

### 4. Fall back to local accumulation if direct quota data is unavailable

If direct quota data cannot be found, implement notifications by recording Codex usage events locally and computing rolling windows.

Recommended model:
- persist each Codex call timestamp
- persist any measurable usage signal available from the request/response
- compute rolling totals over:
  - last 5 hours
  - last 7 days
- derive notification fields:
  - percent used or remaining
  - estimated reset time = oldest event aging out of the active window

## Decision rule

Use direct polling only if you can verify all or most of these from a real authenticated response:
- total quota
- remaining quota or used quota
- reset time

Otherwise use local accumulation.

## Practical output format

Good notification payloads are compact, e.g.:
- `5h: 62% used / reset 03:40 JST`
- `week: 41% used / reset 2026-04-29 03:20 JST (5d 04:18)`

If the user does not want remaining quota, only surface used percent.
For weekly windows, prefer an explicit remaining-duration suffix in the form `5d hh:mm`.

## Recommended monitoring design

When direct quota headers are available from real Codex responses, prefer a hybrid design:

1. Capture Codex quota headers opportunistically on every normal Codex response.
2. Persist the latest snapshot to a profile-local JSON state file.
3. Run a low-frequency timer (for example, once per hour) to evaluate alert conditions and optionally refresh stale data.
4. Notify only on threshold crossings, not every poll.

This avoids extra quota burn from polling on every cycle while keeping alert freshness acceptable.

### Important implementation rule

Do not inject monitoring instructions into the user prompt or agent instructions.
Capture headers at the HTTP client / response layer only.
That preserves the user's original message fidelity and avoids "diluting" the prompt with monitoring text.

### Threshold pattern

A reusable threshold scheme is:
- alert at `85%`
- alert at `90%`
- alert at `95%`

Store alert state so each threshold fires only once per active window.
When the 5-hour or weekly reset timestamp advances past the prior window, clear the corresponding threshold state.

### Multi-profile monitoring

Hermes may have multiple profiles such as `default`, `myknot`, and `mycare`, each with its own `auth.json` and possible `openai-codex` credentials.
A reusable monitor can:
- enumerate profiles
- detect which profiles have Codex auth configured
- collect quota snapshots per profile

However, multiple profiles may share the same underlying ChatGPT/Codex account.
In that case, quota values can be effectively identical and naive per-profile alerting will duplicate notifications.

Recommended approach:
- inspect each profile for Codex auth
- derive a stable account key from the credential source or token identity if possible
- deduplicate alerts across profiles that share the same account
- keep profile-level provenance in the stored snapshot for debugging

### Systemd timer fit

For deterministic notification checks, prefer an LLM-free systemd user timer over a Hermes cron job.
The timer should evaluate stored quota state and only send a Discord message when:
- a threshold is crossed
- the state is stale and a direct refresh is required
- an error requires operator attention

## Implemented reference pattern

The reusable pattern that was actually implemented in this environment is:

### Layout convention

Treat Hermes root vs profiles as:
- `~/.hermes` = global/shared
- `~/.hermes/profiles/<name>` = personal/profile-specific

For a Codex account-level quota monitor, store assets in the global layer, not under a single profile.

Recommended concrete paths:
- global monitor entrypoint:
  - `~/.hermes/global/scripts/codex_quota_monitor.py`
- global config:
  - `~/.hermes/global/config/codex_quota_monitor.json`
- global state:
  - `~/.hermes/global/state/codex_quota_state.json`
- systemd user service/timer:
  - `~/.config/systemd/user/codex-quota-monitor.service`
  - `~/.config/systemd/user/codex-quota-monitor.timer`

### Header capture in Hermes runtime

Hook the HTTP response layer in Hermes, not the prompt layer.

A working integration point is in `run_agent.py`:
- add a response hook method that inspects Codex responses and persists quota headers
- attach it to the `httpx.Client(event_hooks={"response": [...]})` used by the OpenAI client for `codex_responses`

Important details from the implementation:
- only capture when `self.api_mode == "codex_responses"`
- only capture for requests targeting `chatgpt.com/backend-api/codex`
- persist via a helper module, not inline in the hook
- use `display_hermes_home()` or equivalent source labeling for provenance only

This preserves user message fidelity because no prompt text is modified.

### Account deduplication

Do not dedupe by profile name.
Deduplicate by Codex account identity derived from the OAuth access token.

A robust implemented approach was:
1. decode the JWT payload from the Codex access token
2. read `https://api.openai.com/auth.chatgpt_account_id`
3. use that as the primary `account_key`
4. fall back to `sub`, then email, then a token hash only if necessary

This turns multiple profiles sharing one Codex account into one monitored entity and avoids duplicate alerts.

### Monitor behavior

A reusable monitor loop is:
1. load global state
2. enumerate Codex auth entries across root + profiles
3. dedupe to one probe candidate per account
4. issue a low-cost live Codex streaming probe per account
5. update latest snapshot
6. compute threshold crossings for 5h and week independently
7. send Discord only when a new threshold is crossed
8. clear threshold memory automatically when the corresponding reset timestamp changes

### Live probe contract

The successful probe contract stayed minimal:
- `POST https://chatgpt.com/backend-api/codex/responses`
- payload fields:
  - `model`
  - `instructions`
  - `input`
  - `store: false`
  - `stream: true`

Using a tiny request like `Reply with OK only.` is sufficient to obtain the quota headers.

### Notification format

The user-preferred compact format was:
- `5h: 90% used / reset 13:35`
- `week: 86% used / reset 4d 18:27`

Formatting rules:
- JST for displayed times
- weekly line shows remaining duration in `Dd HH:MM`
- omit remaining percentage if the user only wants used percentage

### Suggested config knobs

A simple global config JSON can include:
- `mode`
  - `always` = send the current quota snapshot every run
  - `thresholds` = notify only when new threshold crossings occur
- `probe_model`
- `thresholds` (e.g. `[85, 90, 95]`) when using threshold mode
- Discord delivery target/channel id

### Important implementation update

The implemented monitor was later changed from a single threshold-only flow to a dual-axis notification design.

Current preferred behavior in this environment:
- **Hourly summary axis**
  - systemd timer runs hourly
  - config uses `"mode": "always"`
  - every timer run sends the current snapshot, regardless of threshold crossings
- **Message-event axis**
  - every real Codex response still captures headers immediately at the HTTP hook layer
  - message-event handling computes threshold crossings using `85 / 90 / 95`
  - message-event notifications fire only on first crossing within the active 5h/week window
  - threshold memory clears automatically when the corresponding reset timestamp changes

This means the design is now:
- periodic summaries with **no threshold gate**
- immediate message-time alerts with **threshold gating**

Notification format remains compact:
- `5h: <used>% used / reset HH:MM`
- `week: <used>% used / reset <Dd HH:MM>`

### Suggested config knobs

A simple global config JSON can include:
- `mode`
  - `always` = send the current quota snapshot every timer run
  - `thresholds` = notify only when new threshold crossings occur on the timer path
- `probe_model`
- `thresholds` (e.g. `[85, 90, 95]`) for threshold-based logic
- `delivery.discord_channel_id` for timer-driven summaries
- `message_event`
  - `enabled`
  - `thresholds`
  - `discord_channel_id`

### Runtime split

Implement the two axes separately:

1. **Timer path**
   - use `run_monitor()`
   - probe the live Codex account hourly
   - if `mode == "always"`, send every result
   - if `mode == "thresholds"`, only send new threshold crossings

2. **Message path**
   - use the Codex response hook in `run_agent.py`
   - call a helper such as `process_codex_headers(...)`
   - update global state immediately from real user traffic
   - if `message_event.enabled` is true, compute `due_thresholds(...)`
   - send Discord only when a new threshold is crossed

This keeps user-message-time threshold alerts and timer-based summaries independent while sharing the same global state store.

### Verification steps

After wiring the feature:

```bash
python -m pytest tests/run_agent/test_codex_quota.py tests/run_agent/test_run_agent_codex_responses.py -q
python -m py_compile agent/codex_quota.py
/home/ubuntu/.hermes/hermes-agent/venv/bin/python /home/ubuntu/.hermes/global/scripts/codex_quota_monitor.py
systemctl --user daemon-reload
systemctl --user enable --now codex-quota-monitor.timer
systemctl --user start codex-quota-monitor.service
systemctl --user status codex-quota-monitor.timer --no-pager --full
systemctl --user status codex-quota-monitor.service --no-pager --full
```

Expected healthy behavior:
- tests pass
- manual monitor run prints `[SILENT]` when thresholds are not crossed
- timer is `active (waiting)`
- service may show `inactive (dead)` after success because it is oneshot

## Known findings from prior investigation

- Browser access to OpenAI docs may be blocked by Cloudflare during agent automation.
- In this Hermes environment, `codex` CLI was not installed, so CLI inspection is not a reliable prerequisite.
- Standard unauthenticated calls to `https://api.openai.com/v1/usage` and `.../organization/usage/completions` return 401, which only confirms the endpoints exist, not that they expose Codex 5h/weekly quota data.
- Hermes request dumps confirmed actual Codex traffic to `https://chatgpt.com/backend-api/codex/responses`.
- Codebase searches found no obvious built-in Codex quota endpoint for 5-hour or weekly remaining/reset data.
- Direct `GET` probes to guessed endpoints such as `/codex/usage`, `/codex/limits`, `/codex/rate_limits`, `/codex/subscription`, and `/codex/account` returned 403 and were not the right retrieval path.
- The reusable direct retrieval path was: send a real authenticated streaming request to `POST https://chatgpt.com/backend-api/codex/responses` and read the response headers.
- Important request contract details discovered empirically:
  - `stream` must be `true`
  - minimal working payload was enough: `model`, `instructions`, `input`, `store:false`, `stream:true`
  - `max_output_tokens` was rejected by this backend in the tested direct request with `Unsupported parameter: max_output_tokens`
- A successful streaming response exposed quota metadata in headers, including:
  - `x-codex-primary-used-percent`
  - `x-codex-secondary-used-percent`
  - `x-codex-primary-window-minutes` = 300
  - `x-codex-secondary-window-minutes` = 10080
  - `x-codex-primary-reset-after-seconds`
  - `x-codex-secondary-reset-after-seconds`
  - `x-codex-primary-reset-at`
  - `x-codex-secondary-reset-at`
  - plus plan metadata such as `x-codex-plan-type` and `x-codex-active-limit`
- In the tested account, those headers directly provided the user-requested four monitoring fields:
  - 5-hour used percent / remaining percent
  - 5-hour reset time
  - weekly used percent / remaining percent
  - weekly reset time

## Pitfalls

- Do not promise exact 5h/weekly quota numbers before verifying a real source.
- Do not build on ordinary API rate-limit headers unless the user explicitly wants RPM/TPM alerts.
- Do not conflate ChatGPT/Codex product quotas with OpenAI platform usage billing endpoints.
