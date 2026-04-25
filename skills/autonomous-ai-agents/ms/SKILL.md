---
name: ms
description: Ultra-short alias for session memory curation. Propose add/replace/remove updates for MEMORY.md and USER.md, ask for approval, then apply approved changes.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [memory, session-end, curation, alias, mobile]
---

# ms

This is the shortest mobile-friendly alias for `session-memory-curator`.

Use this near the end of a session, before `/reset`, before ending a long thread, or whenever the user wants to preserve useful context from the conversation.

## Trigger phrases

Treat the following kinds of user messages as a cue to proactively run this flow even if the user does not explicitly invoke a command:

- they say they are ending the session
- they say they are switching or resetting the session
- they say they want to wrap up, close out, or preserve what matters before moving on

Japanese examples:
- `セッション切り替える`
- `セッション終わる`
- `ここで終わり`
- `切り替える前に整理して`
- `終わる前に残すもの見て`

When you detect this intent, do not wait for `/ms` or `/skill`. Start the memory-curation flow directly.

## Goal

Convert valuable session learnings into durable memory **only with user approval**.

This includes:
- **add** for new durable memories
- **replace** when an existing memory is outdated
- **remove** when an existing memory is obsolete or no longer useful

Split candidates into the two built-in memory stores:

- `MEMORY.md` → environment facts, tool quirks, project conventions, stable workflow notes, and assistant-side operating rules
- `USER.md` → user preferences, communication style, recurring requests, and durable expectations about what the user wants

If a fact is mainly about how Hermes should behave internally (triggering, routing, classification, execution policy), store it in `MEMORY.md` rather than `USER.md`.

## Core rules

1. **Do not auto-save without asking.**
2. Only propose durable information likely to matter in future sessions.
3. Exclude temporary task state, one-off progress notes, and completed-task logs.
4. Keep entries short, specific, and standalone.
5. Prefer **replace** over add when an existing entry should be updated.
6. Prefer **remove** when an entry is wrong, obsolete, or noisy.
7. If nothing is worth saving, say so plainly.

## Procedure

### Step 1: Review the session
Look for:
- explicit user corrections
- repeated preferences
- durable environment facts discovered with tools
- stable workflow conventions

### Step 2: Draft candidates
Prepare up to:
- 3 candidates for `MEMORY.md`
- 3 candidates for `USER.md`

Each candidate should be one of:
- `[add] ...`
- `[replace] 旧: "..." → 新: "..."`
- `[remove] "..."`

Prefer fewer. Zero is acceptable.

### Step 3: Ask for approval
Use this format:

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

Keep the durable memory text in English if appropriate, but always attach a Japanese translation when presenting candidates for approval.

If nothing is worth saving:

```markdown
今回の会話では、永続メモリに反映すべき情報は特にありませんでした。
```

### Step 4: Apply only approved items
- **add** → `memory(action="add", ...)`
- **replace** → `memory(action="replace", ...)`
- **remove** → `memory(action="remove", ...)`

### Step 5: Confirm

```markdown
反映しました。
- MEMORY.md: add 1件 / replace 0件 / remove 1件
- USER.md: add 0件 / replace 1件 / remove 0件
```

## Final reminder
This is for **curation**, not indiscriminate logging.
When in doubt, propose fewer candidates and let the user decide.
