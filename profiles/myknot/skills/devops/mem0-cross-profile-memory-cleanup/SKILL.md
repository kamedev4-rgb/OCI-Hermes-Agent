---
name: mem0-cross-profile-memory-cleanup
description: Clean up cross-profile Mem0 contamination by classifying, backing up, compressing, and deleting redundant memories while preserving shared knowledge.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [hermes, mem0, postgres, cleanup, deduplication, profiles]
---

# Mem0 cross-profile memory cleanup

Use when one Hermes profile's Mem0 store contains memories that clearly belong to another profile, but you do **not** want to blindly delete everything.

Typical case:
- MyKNOT DB contains many MyCARE-related memories from earlier shared operation.
- You want to keep only durable shared knowledge and remove noisy migration logs, duplicate status notes, and temporary plans.

## Goal

Reduce cross-profile contamination while preserving:
1. role/identity facts that are useful to the current profile
2. shared integration knowledge
3. one concise stable summary of long-term architectural facts

## Recommended process

### 1. Query candidate rows from PostgreSQL

Example pattern:
- find rows whose JSON payload mentions the other profile name (`mycare`, `MyCARE`)
- inspect `payload->>'data'` and `payload->>'updated_at'`

For the `memories` table used by Mem0 OSS + pgvector:
- table: `memories`
- useful fields live inside `payload` JSONB

### 2. Classify into 3 groups

#### Keep
Keep rows that describe durable shared knowledge:
- profile role/identity
- shared plugins / commands / workflows
- long-term architecture that the current profile should know

#### Compress
Do **not** keep many near-duplicates. Instead, replace them with 1 concise summary memory in the current profile's preferred language.

Good compression targets:
- migration history
- many repeated configuration confirmations
- repeated “we use DB X / profile Y” statements

#### Delete
Delete rows that are mostly noise:
- future-tense plans (`will`, `next step`, `needs to be restarted`)
- step-by-step migration logs
- repeated confirmations of the same fact
- internal settings of the other profile that the current profile does not need

## Practical decision rule

Ask 4 questions for each cluster of rows:
1. Does this help the current profile make better future decisions?
2. Will it still be useful in 30 days?
3. Is it shared integration knowledge rather than one-profile-only detail?
4. Is it a stable fact rather than a temporary step/log?

Decision:
- 3–4 yes -> keep
- 1–2 yes -> compress into one summary memory
- 0 yes / mostly operational chatter -> delete

## Safe execution pattern

### A. Backup first
Before deleting, export the exact rows by UUID to a JSON backup file.
Include:
- row IDs
- full payload JSON
- timestamp

### B. Add compressed replacement memories first
Store the replacement summary facts before deleting the old rows.

Important nuance learned in practice:
- **Display language** and **stored memory language** are not always the same.
- If the user wants English records but needs Japanese explanations, store the memory in **English** and provide **Japanese translation in the chat response**.
- Do not automatically localize the stored memory itself unless the user explicitly wants that.

Also, avoid over-compressing. In practice, **3 summary memories was too aggressive** for a mixed-profile cleanup. A better target is usually **8–10 summary memories**, grouped into layers such as:
1. profile identity / role
2. contamination history (why cleanup was needed)
3. stable architecture facts
4. shared plugin / command integration
5. runtime/profile-location facts when durable
6. cleanup policy / what was intentionally preserved

Example English summaries from a successful cleanup:
- `MyCARE is MyKNOT's separate maintenance and monitoring profile/persona and should be treated as the Maintenance Guardian.`
- `MyCARE and MyKNOT previously shared the same Mem0 store, which caused MyCARE-related memories to mix into MyKNOT's database.`
- `As of 2026-04-21, Mem0 is separated with the 3A layout: MyKNOT uses the myknot database and MyCARE uses the mycare database inside the same PostgreSQL container.`
- `The mycare_approval integration is shared between MyCARE and MyKNOT and handles approval-token issuance, validation, and Discord user-ID binding.`
- `The shared MyCARE/MyKNOT approval-token workflow exposes /mycare-issue-token and /mycare-validate-token.`
- `MyCARE runs under the mycare profile with HERMES_HOME=/home/ubuntu/.hermes/profiles/mycare, while MyKNOT runs under its own profile.`
- `The mycare_approval plugin exists in both the MyKNOT and MyCARE profiles and is part of their shared coordination surface.`
- `Profile-local Mem0 isolation is the intended default for MyCARE-related profile architecture: each profile should have its own mem0.json and its own PostgreSQL database.`

### C. Delete only the backed-up UUID set
Delete by explicit UUID list, never by a broad text pattern alone.

## Verification

After cleanup:
1. re-run the profile-name query (e.g. `%mycare%`)
2. confirm only the intended summary rows remain
3. confirm backup file exists
4. confirm shared integration facts still retrieve correctly

## Lessons learned

- Cross-profile contamination can be large even after DB separation; old shared memories remain in the old DB.
- Compression is better than naive deletion because some shared facts are genuinely useful.
- Doing the cleanup in the user's language improves future retrieval usefulness.
- Backup-before-delete is mandatory for Mem0 cleanup.
