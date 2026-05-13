---
name: bmad-lite-orchestrator
description: "複雑な依頼の入口で、BMAD視点を軽量に選び、必要ならUX設計・仕様化・実装規律へ接続する。"
description_full: "Use for complex MyKNOT tasks that need requirement shaping, product/architecture/QA perspectives, UI/UX gating, or spec-driven execution. Keeps workflows lightweight and uses closed questions before heavy work."
version: 1.0.0
author: MyKNOT
metadata:
  hermes:
    tags: [bmad, orchestration, planning, ux, spec-driven, myknot]
triggers:
  - "新機能"
  - "仕様が曖昧"
  - "複数工程"
  - "設計判断"
  - "UX"
  - "UI改善"
  - "複雑な依頼"
---

# BMAD Lite Orchestrator

## When to use

Use this skill as the lightweight intake for complex work before implementation.

Use it when the request involves one or more of:

- New feature or product change
- Ambiguous requirements
- Multiple files, multiple steps, or multi-session work
- Design, product, architecture, or QA judgment
- User experience or interface impact
- Correct-course / direction change
- Self-refactor that needs extra design thinking

Do **not** use it for:

- Small bug fixes with obvious scope
- Simple text/content changes
- Minor config edits
- Clear one-step operations
- Emergency fixes where the user already gave exact steps

## Non-negotiable constraints

- For self-modification of MyKNOT/Hermes, `self-refactor` has priority and this skill is only auxiliary.
- If UI/UX is involved, route through `bmad-ux-gate` before implementation planning.
- Claude Code is thinking support only. Do not ask Claude Code to edit files, run tests to completion, commit/push, deploy, restart, or make final user-facing decisions.
- Keep automation light. Ask a closed question before entering a heavy workflow unless the user already explicitly authorized it.
- Do not add SOUL rules unless skills alone are insufficient.

## BMAD perspectives

Select only the perspectives needed for the task:

- **Analyst**: clarify situation, facts, constraints, unknowns
- **PM**: goal, scope, non-goals, success metrics, priority
- **UX Designer**: user flow, screen structure, mobile/PC behavior, accessibility
- **Architect**: system boundaries, data flow, integration risks
- **Dev**: implementation strategy, file/module impact, testability
- **QA**: acceptance criteria, regression risks, verification evidence
- **Correct Course**: identify drift, simplify, revise direction

## Workflow

1. Classify the task:
   - light work
   - complex work
   - UI/UX work
   - self-refactor
   - research/design only
2. State the recommended path briefly.
3. If the path is heavy or changes scope, ask a closed question:
   - `I would proceed with X because Y. Is that okay?`
4. For UI/UX work, load and follow `bmad-ux-gate` before implementation planning.
5. For complex implementation, load and follow `spec-driven-autonomy` to produce or update spec artifacts.
6. During implementation, use existing Superpowers-style skills where applicable: test-driven-development, requesting-code-review, systematic-debugging, subagent-driven-development.
7. Verify against explicit acceptance criteria before reporting completion.
8. Save durable learnings to memory/skills only when they will matter in future sessions.

## Minimal intake output

For most tasks, keep the intake compact:

```text
分類: <light|complex|uiux|self-refactor|research>
使う視点: <PM, UX, Architect, QA...>
推奨経路: <direct|ux-gate|spec-driven|self-refactor + auxiliary>
確認: <closed question if needed>
```

## Claude Code use

Use Claude Code only for thinking tasks, for example:

- Requirement gap analysis
- Design option comparison
- UX review viewpoints
- Risk inventory
- Task granularity review
- Post-implementation review checklist
- Bug-cause hypothesis整理

Never delegate implementation, file edits, tests-as-completion, git operations, deployment, restart, or final approval to Claude Code.

## Completion criteria

This orchestration step is complete when:

- The task category is clear.
- Needed BMAD perspectives are selected.
- UI/UX work is routed to `bmad-ux-gate`.
- Complex implementation is routed to `spec-driven-autonomy`.
- The user is not forced into unnecessary heavy process.
