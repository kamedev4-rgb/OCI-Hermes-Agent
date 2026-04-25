---
name: hermes-cron-failure-audit
description: Audit recurring Hermes cron job failures by separating script/runtime issues from upstream LLM/provider failures, quantifying error patterns, and identifying when simple monitor jobs should not use a full agent turn.
version: 1.0.0
metadata:
  hermes:
    tags: [hermes, cron, debugging, mycare, ops, provider-failures]
    related_skills: [systematic-debugging, hermes-agent]
---

# Hermes Cron Failure Audit

Use when a Hermes profile has cron jobs that intermittently fail and the question is "what is actually causing these errors?"

## Goal

Determine whether the failures come from:
1. the pre-run script,
2. Hermes cron/gateway orchestration,
3. the model provider / upstream API,
4. or prompt/tool inflation that makes trivial cron jobs unnecessarily expensive.

## Procedure

### 1. Inspect active jobs first

Run:
```bash
hermes --profile <profile> cron list
hermes --profile <profile> cron status
```

Then read:
- `<profile>/cron/jobs.json`

Capture for each job:
- job id / name
- schedule
- script path
- deliver target
- last status

### 2. Read actual cron output artifacts

Check:
- `<profile>/cron/output/<job_id>/*.md`

Important distinction:
- If the markdown shows normal `## Script Output` but `## Response` contains `API call failed after 3 retries`, the script likely worked and the failure happened during LLM response generation.
- If script output is malformed or missing, investigate the script itself.

### 3. Correlate with logs and request dumps

Search in:
- `<profile>/logs/errors.log`
- `<profile>/logs/agent.log`
- `<profile>/sessions/request_dump_cron_*.json`

Look specifically for:
- `HTTP 429`
- `HTTP 500`
- `The usage limit has been reached`
- `Our servers are currently overloaded`
- `request_dump_cron`

Request dumps are the best evidence for root cause because they show:
- target endpoint
- provider/model
- full prompt shape
- message count / token count
- whether tools/skills were invoked before failure

Important format note:
- In current Hermes request dumps, the useful payload may be nested under `request.body` rather than top-level fields.
- If top-level `model`, `messages`, or `provider` look empty/null, inspect `request.url`, `request.body.model`, `request.body.input`, and `request.body.tools` before concluding the dump is unhelpful.

### 4. Quantify the pattern instead of eyeballing it

Count failures by job and provider, and compare token sizes. A simple Python one-liner via `terminal` is enough.

What to measure:
- failure count per job
- average/min/max tokens per failed request
- provider distribution (`openai-codex`, `nvidia`, etc.)
- how many outputs are `[SILENT]` vs error vs real report

This often reveals that a monitor job fails only occasionally, while most runs are actually trivial no-op checks.

### 5. Inspect profile config for structural causes

Read `<profile>/config.yaml` and check:
- `model.provider`
- `model.default`
- `fallback_providers`
- any profile-specific prefill/personality settings if response verbosity matters

Key finding to look for:
- `fallback_providers: []` means upstream 429/500 errors have no escape path and will surface directly as cron errors.

### 6. Check whether the job is overusing the agent

For simple monitor jobs, compare the script output with the request dump.

Red flag pattern:
- script output is tiny and deterministic
- desired behavior is just `[SILENT]` unless alerts exist
- but request dumps show thousands of tokens and tool/skill calls such as `skills_list` / `skill_view`
- or an obviously unrelated skill gets loaded (for example `daily_check` during a Docker monitor no-op run), inflating the request for no operational benefit

This means the cron job is using a full agent turn for a decision that should probably be made in the script itself.

## Interpretation guide

### A. Script is healthy, provider is failing

Evidence:
- cron output contains valid script JSON
- response section shows `API call failed after 3 retries`
- logs show 429/500/overloaded errors
- request dump endpoint/provider is external

Conclusion:
- root cause is upstream provider failure, not the monitoring script.

### B. Job is structurally fragile

Evidence:
- most runs should be `[SILENT]`
- failed requests still consume ~4k+ tokens
- tool/skill calls appear in request dumps for trivial checks

Conclusion:
- the cron design is overpowered for the task; even if provider reliability improves, the setup wastes tokens and will keep being fragile.

## Recommended fixes to propose

Order from safest to strongest:

1. **Add fallback providers**
   - Prevent transient provider failures from surfacing directly.

2. **Move silent/report branching into the script**
   - For monitor jobs, let the script emit either a final human message or a sentinel that means no delivery.
   - Best when the result is deterministic and does not need reasoning.

3. **Reduce prompt/tool overhead**
   - Avoid loading unrelated skills for trivial cron jobs.
   - Keep prompt minimal.

4. **Reserve full agent runs for jobs that truly need synthesis**
   - Example: daily health reports or multi-signal diagnosis.
   - Do not use the same heavy path for “nothing changed” heartbeat checks.

## MyCARE-specific lesson captured here

In the MyCARE monitor case, the reusable pattern was:
- `docker_monitor.py` and `oci_monitor.py` returned simple JSON correctly,
- cron outputs showed failure only in the LLM response section,
- request dumps proved the jobs were calling the OpenAI Codex endpoint,
- logs showed recurring upstream 500/429/overload errors,
- and the jobs were spending thousands of tokens to decide whether to emit `[SILENT]`.

So the correct diagnosis was: **not a script bug, but provider-side failures amplified by an over-heavy cron design and lack of fallback.**
