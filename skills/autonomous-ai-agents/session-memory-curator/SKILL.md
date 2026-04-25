---
name: session-memory-curator
description: At the end of a session, extract candidate durable memories from the conversation, separate them into MEMORY.md vs USER.md, ask the user whether to save them, and only then write approved entries with the memory tool.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [memory, session-end, curation, hermes, user-profile]
---

# Session Memory Curator

Use this skill near the end of a session, before `/reset`, before ending a long thread, or whenever the user asks to preserve useful context from the conversation.

## Goal

Convert valuable session learnings into durable memory **only with user approval**.

This includes not only **new additions**, but also:
- **replacements** when an existing memory has become outdated
- **removals** when an existing memory is no longer useful or has been superseded

Split candidates into the two built-in memory stores:

- `MEMORY.md` → environment facts, tool quirks, project conventions, stable workflow notes
- `USER.md` → user preferences, communication style, recurring requests, durable personal/workflow expectations

## Core rules

1. **Do not auto-save candidates without asking.**
2. Only propose **durable** information that is likely to matter in future sessions.
3. Exclude temporary task state, one-off progress notes, and completed-task logs.
4. Keep every proposed entry short, specific, and standalone.
5. If nothing is worth saving, say so plainly instead of forcing entries.
6. After approval, write approved changes with the `memory` tool.
7. If the user edits a proposed entry, save the edited version, not the original.
8. Prefer **replace** over add when an existing entry is now outdated.
9. Prefer **remove** when an entry has become wrong, obsolete, or no longer useful.

## What belongs where

### Propose for `MEMORY.md`

Good candidates:
- stable environment facts
- repo/project conventions
- discovered tool limitations or quirks
- durable workflow rules
- implementation constraints likely to recur

Do **not** propose:
- current branch/task progress
- ephemeral bug states
- one-time outputs/results
- long procedural writeups better saved as skills

### Propose for `USER.md`

Good candidates:
- communication preferences
- tone/format preferences
- repeated corrections
- approval boundaries
- recurring operational preferences that describe what the user wants
- standing dislikes / do-not-do rules

Do **not** put assistant-side trigger logic or internal operating rules here. If the information is primarily about how Hermes should route, trigger, classify, or execute behavior, it belongs in `MEMORY.md`, even if it was caused by a user request.

Do **not** propose:
- temporary moods
- session-specific decisions
- sensitive details unless clearly appropriate and useful
- facts that are trivial or unlikely to matter again

## Extraction procedure

### Step 1: Review the current session

Mentally scan the session for:
- explicit user corrections
- repeated user preferences
- durable environment facts discovered with tools
- conventions that will likely matter again

### Step 2: Draft candidates

Prepare up to:
- 3 candidates for `MEMORY.md`
- 3 candidates for `USER.md`

For each candidate, choose one action:
- **add**
- **replace**
- **remove**

Prefer fewer. Zero is acceptable.

For **add** and **replace**, each candidate should be a single short sentence.
For **replace** and **remove**, identify the existing entry by a short unique substring that can be used with the `memory` tool.

### Step 3: Present for approval

Use this response format:

```markdown
残しておくと役立ちそうな候補を整理しました。

### MEMORY.md 候補
1. [add] EN: ...
   JA: ...
2. [replace] 旧 EN: "..."
   旧 JA: "..."
   新 EN: "..."
   新 JA: "..."
3. [remove] EN: "..."
   JA: "..."

### USER.md 候補
4. [add] EN: ...
   JA: ...
5. [replace] 旧 EN: "..."
   旧 JA: "..."
   新 EN: "..."
   新 JA: "..."

反映するものを番号で指定してください。不要なら「なし」で大丈夫です。
```

Write the actual memory entry in English if that is the preferred durable form, but always include a natural Japanese translation for user review when presenting candidates.

If there are no candidates in one section, write `- なし`.
If there are no candidates at all, say:

```markdown
今回の会話では、永続メモリに反映すべき情報は特にありませんでした。
```

### Step 4: Ask explicitly

After listing candidates, ask the user which ones to save.
Use `clarify` when appropriate.

Recommended wording:
- `どれを保存しますか？番号で指定してください。修正して保存したい場合は、その文面を書いてください。`

### Step 5: Save only approved items

For each approved candidate:

- if action is **add**:
  - save to `target="memory"` for `MEMORY.md`
  - save to `target="user"` for `USER.md`
  - use `memory(action="add", ...)`

- if action is **replace**:
  - use `memory(action="replace", target=..., old_text=..., content=...)`

- if action is **remove**:
  - use `memory(action="remove", target=..., old_text=...)`

If the user gives revised wording, save the revised wording.

### Step 6: Confirm result

After writing, respond with a short confirmation:

```markdown
反映しました。
- MEMORY.md: add 1件 / replace 0件 / remove 1件
- USER.md: add 0件 / replace 1件 / remove 0件
```

If some approved item is already present, mention that it was skipped as duplicate.

## Compression / reset timing

Use this skill especially:
- right before `/reset`
- right before ending a long session
- after a meaningful correction from the user
- after discovering a durable environment fact

## When to create a skill instead of memory

If the learned content is a reusable multi-step procedure, save it as a **skill**, not a memory entry.

Rule of thumb:
- short enduring fact/preference → memory
- reusable workflow with steps/pitfalls → skill

## Good example

```markdown
残しておくと役立ちそうな候補を整理しました。

### MEMORY.md 候補
1. This Hermes environment has agent-browser CLI installed and working.
2. The current project prefers Discord-side self-service controls when feasible.

### USER.md 候補
3. The user prefers precise explanations of memory architecture.
4. The user does not want automatic skill auto-loading unless clearly necessary.

どれを保存しますか？番号で指定してください。修正して保存したい場合は、その文面を書いてください。
```

## Bad example

Do not propose noisy entries like:
- `Today we discussed memory.`
- `The user asked about files.`
- `We fixed one issue in this session.`
- `The assistant used several tools successfully.`

## Final reminder

This skill is for **curation**, not indiscriminate logging.
When in doubt, propose fewer candidates and let the user decide.
