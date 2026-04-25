---
name: hermes-rate-limit-and-media-path-bugfixes
description: Fix Hermes-specific bugs where provider 429 payloads expose resets_in_seconds and gateway MEDIA tags accidentally pass placeholder or missing file paths.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, gateway, rate-limit, media, regression-tests, tdd]
    related_skills: [systematic-debugging, test-driven-development]
---

# Hermes rate-limit and MEDIA path bugfixes

Use when Hermes shows either of these symptoms:
- provider 429 / usage_limit_reached errors with `resets_in_seconds` in logs, but credentials stay exhausted too long
- gateway warnings like `Failed to send media (): File not found: <screenshot_path>`

## Root causes

### 1. `resets_in_seconds` not converted
In `run_agent.py`, `_extract_api_error_context()` may capture `resets_at` / `retry_after` but miss `resets_in_seconds`. If so, credential pool falls back to the default 429 exhausted TTL instead of the provider's actual reset time.

### 2. Placeholder MEDIA paths accepted
In `gateway/platforms/base.py`, `extract_media()` can parse placeholder strings like `<screenshot_path>` unless validation rejects them. Later send logic then tries to attach a nonexistent file.

### 3. Misleading browser tool guidance
In `tools/browser_tool.py`, avoid telling the model to literally emit `MEDIA:<screenshot_path>`. It should use the returned `screenshot_path` value, not the placeholder text.

## Required fixes

### A. Rate-limit reset handling
Add support in `run_agent.py::_extract_api_error_context()`:
- if payload includes `resets_in_seconds`
- and no explicit `reset_at` / `resets_at` was already set
- compute `reset_at = time.time() + float(resets_in_seconds)`

### B. MEDIA path validation
In `gateway/platforms/base.py::extract_media()`:
- accept only actual local path forms:
  - `/absolute/path`
  - `~/home-relative/path`
- reject placeholders / wrapped dummy tokens like:
  - `<screenshot_path>`
  - `{screenshot_path}`
  - other bracketed non-path placeholders
- still strip the invalid `MEDIA:` tag from cleaned text so the user does not see internal syntax

### C. Existence check before send
In `BasePlatformAdapter._process_message_background()`:
- before routing a `media_path` to `send_voice`, `send_video`, `send_image_file`, or `send_document`
- verify `os.path.isfile(media_path)`
- if missing: log warning and `continue`

### D. Tool description fix
In `tools/browser_tool.py`, update `browser_vision` description to say:
- it returns `screenshot_path`
- callers should use the returned `screenshot_path` value in `MEDIA:`
- do **not** mention the literal `MEDIA:<screenshot_path>` placeholder as if it were valid output

## Regression-test pattern
Follow strict TDD.

### Tests to add
1. `tests/run_agent/test_run_agent.py`
   - add a case proving `_extract_api_error_context()` converts `resets_in_seconds` into numeric `reset_at`
   - patch `time.time()` for deterministic assertion

2. `tests/gateway/test_platform_base.py`
   - add a case proving `extract_media()` rejects `<screenshot_path>` / `{screenshot_path}`
   - add a source-level or behavioral regression asserting `_process_message_background()` checks file existence before sending

3. `tests/tools/test_browser_tool_media_guidance.py`
   - assert `browser_vision` description does not contain literal `MEDIA:<screenshot_path>`
   - assert it references the returned `screenshot_path` value instead

## Verification commands
Run targeted tests first:
```bash
pytest tests/run_agent/test_run_agent.py -k extract_api_error_context -q
pytest tests/gateway/test_platform_base.py -k 'placeholder_paths or media_file_exists_before_sending' -q
pytest tests/tools/test_browser_tool_media_guidance.py -q
```

Then run the touched suites together:
```bash
pytest tests/run_agent/test_run_agent.py tests/gateway/test_platform_base.py tests/tools/test_browser_tool_media_guidance.py -q
```

## Expected outcome
- 429 payloads with `resets_in_seconds` recover using actual provider reset timing
- placeholder media tags are ignored rather than sent
- nonexistent media files are skipped safely with a warning
- browser tool guidance no longer encourages placeholder misuse
