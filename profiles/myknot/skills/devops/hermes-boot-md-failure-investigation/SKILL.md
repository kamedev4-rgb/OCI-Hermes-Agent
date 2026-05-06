---
name: hermes-boot-md-failure-investigation
description: Investigate why Hermes gateway startup ran BOOT.md but did not complete self-refactor-post or clear ~/.hermes/BOOT.md.
version: 1.0.0
author: MyKNOT
license: CC0-1.0
---

# hermes-boot-md-failure-investigation

## When to use

Use when all or most of these are true:

- gateway restart happened
- `hooks.boot-md: Running BOOT.md` appears in logs
- `~/.hermes/BOOT.md` still exists afterward
- post-restart task (often `self-refactor-post`) did not finish
- `agent.log` shows provider/API errors during boot
- you need to determine whether the issue is hook startup, provider failure, result handling, or BOOT.md-clearing logic

## Goal

Determine, with code and log evidence, why boot started but did not complete, and whether the behavior is expected or a bug.

## Files to inspect first

- `~/.hermes/BOOT.md`
- `~/.hermes/profiles/<profile>/logs/agent.log`
- `~/.hermes/hermes-agent/gateway/builtin_hooks/boot_md.py`
- `~/.hermes/hermes-agent/run_agent.py`
- `~/.hermes/hermes-agent/gateway/run.py`
- `~/.hermes/profiles/<profile>/skills/self-refactor-post/SKILL.md`
- `~/.hermes/profiles/<profile>/config.yaml`

## Investigation steps

1. Confirm the BOOT target file.
   - Check whether the active code reads `~/.hermes/BOOT.md` or a profile-local `BOOT.md`.
   - Current built-in boot hook should read the root file: `~/.hermes/BOOT.md`.

2. Confirm the startup sequence from logs.
   - Search `agent.log` for:
     - `Running BOOT.md`
     - `boot-md completed`
     - `boot-md agent failed`
     - `Non-retryable client error`
   - Capture the exact timestamp window around restart.

3. Read `boot_md.py` and classify its behavior.
   - `handle()` only checks file existence/content and starts a daemon thread.
   - `_run_boot_agent()` builds a one-shot `AIAgent`, calls `run_conversation()`, then logs based on `final_response`.
   - Important: current logic treats falsy `final_response` as `completed (nothing to report)` unless an exception escapes.

4. Check how `run_conversation()` reports failures.
   - In `run_agent.py`, non-retryable client errors can return a dict like:
     - `final_response: None`
     - `completed: False`
     - `failed: True`
     - `error: ...`
   - This means boot can fail without raising an exception to `boot_md.py`.

5. Inspect request dumps for the boot session.
   - Request debug dumps are written under:
     - `~/.hermes/profiles/<profile>/sessions/request_dump_<session_id>_*.json`
   - Search by boot session ID from the log line prefix, e.g. `[20260429_033341_bf8089]`.
   - These dumps often show the true HTTP status and provider body even when `agent.log` truncates to `<html>`.

6. Check fallback availability.
   - In `config.yaml`, inspect `fallback_providers`.
   - If it is empty, provider failures during boot will not switch to another model/provider.

7. Check where BOOT clearing actually happens.
   - For self-refactor flows, `BOOT.md` is usually cleared by `self-refactor-post` Step 3, not by the hook itself.
   - Therefore, if the boot agent never reaches that step, `BOOT.md` remaining is expected.

## Known failure pattern

A common pattern is:

1. `hooks.boot-md: Running BOOT.md ...`
2. provider call fails (for example 403/401/400)
3. `run_conversation()` returns `failed=True, final_response=None`
4. `boot_md.py` ignores `failed` and only checks `final_response`
5. log says `boot-md completed (nothing to report)`
6. `BOOT.md` remains because post-task never reached the clearing step

## Important code-reading conclusions

### boot_md.py failure handling

Current boot hook behavior is weak because it effectively distinguishes only:

- exception escaped from `run_conversation()` -> `boot-md agent failed`
- anything else with falsy response -> `boot-md completed (nothing to report)`

That means returned failure dicts are misclassified as success/silence.

### run_agent.py failure contract

For non-retryable client/provider failures, the agent may return a result dict instead of raising.
This is normal and is also used by the gateway main path.

### BOOT.md remaining

If `self-refactor-post` never completed, BOOT remaining is not itself a separate bug. The real bug is misclassification/logging of boot result state.

## How to answer the root-cause question

Structure the conclusion like this:

- hook startup status: started successfully
- provider/API status: failed during boot agent execution
- return contract: `run_conversation()` returned `failed=True` result rather than raising
- direct cause of misleading log: `boot_md.py` checked `final_response` only
- BOOT retention: happened because post-task never reached the explicit clear step
- classification: misleading `completed (nothing to report)` is a bug; BOOT remaining after failure is desirable behavior if failure is detected honestly

## Minimal fix direction

Usually the smallest correct fix is in:

- `~/.hermes/hermes-agent/gateway/builtin_hooks/boot_md.py`
- plus tests in `~/.hermes/hermes-agent/tests/gateway/test_boot_md.py`

The minimal behavior change should be:

- if `result.get("failed")` or `not result.get("completed")`, log boot failure/incomplete
- only treat `[SILENT]` or empty response as success when the result is actually completed
- preserve `BOOT.md` on failure
- clear `BOOT.md` only after a confirmed successful post-task path

## Pitfalls

- Do not assume `boot-md completed (nothing to report)` means success.
- Do not look only in `logs/` for request dumps; they are stored under `sessions/`.
- Do not treat `BOOT.md` remaining as proof the file was never read; it can also mean it was read but execution failed before the clear step.
- Do not assume provider fallback existed; verify `fallback_providers` in config.

## Verification checklist

- `Running BOOT.md` found in log
- boot session ID identified
- corresponding request dump located in `sessions/`
- provider HTTP status/body confirmed
- `run_conversation()` failure return path located in code
- `boot_md.py` logging branch confirmed
- `self-refactor-post` clear step confirmed
- final conclusion separates true failure from misleading completion log
