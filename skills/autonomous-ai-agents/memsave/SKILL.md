---
name: memsave
description: Short alias for session-memory-curator. At session end, propose add/replace/remove memory updates for MEMORY.md and USER.md, ask for approval, then apply approved changes.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [memory, session-end, curation, alias]
---

# memsave

This is a short mobile-friendly alias for `session-memory-curator`.

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

## Extraction procedure

### Step 1: Review the current session
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

### Step 3: Present for approval
Use this response format:

```markdown
残しておくと役立ちそうな候補を整理しました。

### MEMORY.md 候補
1. [add] ...
2. [replace] 旧: "..." → 新: "..."
3. [remove] "..."

### USER.md 候補
4. [add] ...
5. [replace] 旧: "..." → 新: "..."

反映するものを番号で指定してください。不要なら「なし」で大丈夫です。
```

If there are no candidates in one section, write `- なし`.
If there are no candidates at all, say:

```markdown
今回の会話では、永続メモリに反映すべき情報は特にありませんでした。
```

### Step 4: Ask explicitly
Ask:
- `どれを反映しますか？番号で指定してください。修正して反映したい場合は、その文面を書いてください。`

### Step 5: Apply only approved items
- **add** → `memory(action="add", ...)`
- **replace** → `memory(action="replace", ...)`
- **remove** → `memory(action="remove", ...)`

### Step 6: Confirm result

```markdown
反映しました。
- MEMORY.md: add 1件 / replace 0件 / remove 1件
- USER.md: add 0件 / replace 1件 / remove 0件
```

## Final reminder
This skill is for **curation**, not indiscriminate logging.
When in doubt, propose fewer candidates and let the user decide.
