---
name: spec-driven-autonomy
description: "BMADで整理した内容をSpec Kit形式の成果物へ落とし、Superpowers式の実装・検証規律へ接続する統合ワークフロー。"
description_full: "Use for complex implementation work after intake/UX decisions. Produces specs, plans, tasks, checklists, decisions, then executes with disciplined verification."
version: 1.0.0
author: MyKNOT
metadata:
  hermes:
    tags: [spec-kit, bmad, superpowers, implementation, planning, verification, myknot]
triggers:
  - "spec"
  - "plan"
  - "tasks"
  - "実装計画"
  - "仕様化"
  - "検証まで"
  - "複雑実装"
---

# Spec Driven Autonomy

## Purpose

Use this skill to convert clarified requirements into a small set of durable artifacts, then implement and verify in disciplined steps.

This skill connects:

```text
BMAD = upstream thinking and UX/design judgment
Spec Kit = artifact format
Superpowers = implementation discipline
MyKNOT/Hermes = execution, verification, final responsibility
```

## When to use

Use after `bmad-lite-orchestrator` when a task is complex enough to need artifacts before implementation.

Use for:

- Multi-step feature work
- Multi-file changes
- Work that spans UX, data, backend, and tests
- Tasks where acceptance criteria must be preserved across sessions
- Work that benefits from small, reviewable tasks

Do not use for clear one-step work.

## Required precedence

- If this is MyKNOT/Hermes self-modification, follow `self-refactor` first. This skill cannot override self-refactor safety steps.
- If UI/UX is involved, complete `bmad-ux-gate` before finalizing implementation tasks.
- Claude Code is thinking support only. Do not delegate implementation, file edits, tests-as-completion, git operations, deploy, restart, or final approval to Claude Code.

## Artifact location

Preferred project-local path:

```text
docs/specs/<topic>/
  brief.md
  prd.md
  ux-design.md       # required when UI/UX is involved
  spec.md
  plan.md
  tasks.md
  checklist.md
  decisions.md
```

If the project has another established spec location, use that and mention it.

## Artifact responsibilities

- `brief.md`: short purpose, background, constraints, success conditions
- `prd.md`: user value, scope, non-goals, requirements
- `ux-design.md`: UX decisions and acceptance criteria; required for UI/UX work
- `spec.md`: functional/technical behavior to implement
- `plan.md`: ordered implementation strategy and affected files
- `tasks.md`: small verifiable tasks, each with expected evidence
- `checklist.md`: final acceptance and regression checks
- `decisions.md`: key decisions, rejected alternatives, rationale

## Workflow

1. Confirm the task is not light work.
2. Gather or synthesize `brief.md` and `prd.md` from the conversation/shared note.
3. If UI/UX is involved, run `bmad-ux-gate` and create/update `ux-design.md`.
4. Write `spec.md` with concrete behavior and non-goals.
5. Write `plan.md` with implementation order and impacted files.
6. Write `tasks.md` with small task units:
   - objective
   - files likely affected
   - implementation notes
   - verification command/evidence
7. Write `checklist.md` for final acceptance.
8. Track decisions in `decisions.md` when the design contains trade-offs.
9. Implement task-by-task with existing development skills:
   - `test-driven-development` where feasible
   - `systematic-debugging` for failures
   - `requesting-code-review` before commit/push when code changes are non-trivial
10. Verify against the checklist and report evidence, not just completion.
11. Save durable lessons to memory or skills when reusable.

## Claude Code thinking-support points

Use Claude Code only when it improves thinking quality, e.g.:

- Review requirement gaps in `spec.md`
- Compare implementation approaches
- Review `tasks.md` granularity
- Identify risks before implementation
- Suggest post-implementation review criteria

MyKNOT must decide what to accept and must perform or direct actual implementation with Hermes tools/subagents, not Claude Code.

## Minimal mode

If full artifacts would be excessive, create a compact spec bundle in one file:

```text
docs/specs/<topic>/spec.md
```

It must still include:

- Purpose
- Scope / non-goals
- Requirements
- UX decisions if relevant
- Plan
- Tasks
- Acceptance checklist
- Decisions

## Completion criteria

Work under this skill is complete only when:

- Required artifacts exist or the minimal-mode artifact explicitly covers them.
- UI/UX work has `ux-design.md` or equivalent accepted UX section.
- Tasks are small enough to verify independently.
- Verification evidence is captured.
- Final report maps outcomes back to acceptance criteria.
