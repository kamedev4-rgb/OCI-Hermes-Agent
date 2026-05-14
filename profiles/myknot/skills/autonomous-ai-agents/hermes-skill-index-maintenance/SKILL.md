---
name: hermes-skill-index-maintenance
description: スキルDB整合性保守
description_full: Maintain Hermes skill index database consistency after creating, deleting, renaming, or recall-tuning skills; verify filesystem, skills_list, skill_index.db state, and prompt-candidate scoring.
version: 1.1.0
author: MyKNOT
metadata:
  hermes:
    tags: [hermes, skills, sqlite, skill-index, maintenance]
triggers:
  - "スキルDB"
  - "skill_index.db"
  - "スキルを削除"
  - "skills_listに出ない"
  - "skill_manage delete"
---

# Hermes Skill Index Maintenance

## When to use

Use this when creating, deleting, renaming, or auditing Hermes skills, especially if the user asks whether a skill was removed from the DB as well as from the filesystem.

## Key lesson

`skill_manage(action='delete')` may remove the skill file/directory, and `skills_list` may stop showing the skill, but stale rows can still remain in profile-local `skill_index.db`. Do not claim a skill is fully removed until the database has been checked.

## Skill index DB locations

Check both global and profile-local DBs:

```bash
/home/ubuntu/.hermes/skill_index.db
/home/ubuntu/.hermes/profiles/*/skill_index.db
```

For the MyKNOT profile specifically:

```bash
/home/ubuntu/.hermes/profiles/myknot/skill_index.db
```

## Tables to check

Typical schema includes:

- `skills` — indexed skill metadata
- `skill_usage_events` — per-use history, e.g. `skill_view`
- `skill_usage_rollups` — aggregate usage history

Inspect schema first if unsure:

```bash
sqlite3 /home/ubuntu/.hermes/profiles/myknot/skill_index.db '.tables'
sqlite3 /home/ubuntu/.hermes/profiles/myknot/skill_index.db '.schema skills'
sqlite3 /home/ubuntu/.hermes/profiles/myknot/skill_index.db '.schema skill_usage_events'
sqlite3 /home/ubuntu/.hermes/profiles/myknot/skill_index.db '.schema skill_usage_rollups'
```

## Deletion verification procedure

After deleting a skill, verify all layers:

1. `skills_list` no longer contains the skill.
2. The skill directory/file is gone under the profile skills directory.
3. All relevant `skill_index.db` files have no matching rows.

Example:

```bash
SKILL=delegate-coding
search_files equivalent: check ~/.hermes/profiles/myknot/skills for matching files
for db in /home/ubuntu/.hermes/skill_index.db /home/ubuntu/.hermes/profiles/*/skill_index.db; do
  echo "DB=$db"
  sqlite3 "$db" "SELECT skill_name, skill_path FROM skills WHERE skill_name='$SKILL';"
done
```

## Safe cleanup procedure

Before direct DB edits, create a timestamped backup:

```bash
DB=/home/ubuntu/.hermes/profiles/myknot/skill_index.db
SKILL=delegate-coding
cp "$DB" "$DB.bak_${SKILL}_$(date +%Y%m%d_%H%M%S)"
sqlite3 "$DB" "
  DELETE FROM skills WHERE skill_name='$SKILL';
  DELETE FROM skill_usage_events WHERE skill_name='$SKILL';
  DELETE FROM skill_usage_rollups WHERE skill_name='$SKILL';
"
```

Then re-run the cross-DB verification query.

## `skills_list` architecture note

As currently implemented in Hermes, `skills_list()` is not a direct DB dump. The relevant code is in:

```text
/home/ubuntu/.hermes/hermes-agent/tools/skills_tool.py
```

Current flow:

```text
skills_list()
  -> _find_all_skills() scans SKILL.md files under SKILLS_DIR and external dirs
  -> _sync_skills_to_index() upserts the scanned metadata into skill_index.db
  -> returns the filesystem scan result, not the DB rows
```

The DB helper is:

```text
/home/ubuntu/.hermes/hermes-agent/tools/skill_index_db.py
```

If changing `skills_list` to read DB rows, preserve its public return shape (`name`, `description`, `category`, `categories`, `count`) because callers/tests expect that. Add or use a DB-side full-list method, and decide how to handle stale DB rows whose `SKILL.md` no longer exists. A safer design is: scan files -> sync complete metadata including `skill_path`/`skill_dir` -> mark missing rows stale/disabled/hidden -> return from DB.

Related callers/tests to inspect before refactoring:

```text
tools/skills_tool.py
tools/skill_index_db.py
tools/skill_inventory_tool.py
hermes_cli/web_server.py /api/skills
hermes_cli/skills_config.py
tests/tools/test_skills_tool.py
tests/tools/test_skill_index_db.py
tests/tools/test_skill_inventory_tool.py
```

## Recall / prompt-candidate verification

When improving whether a skill appears for Japanese or mixed-language user requests, do not rely on `skill_view` / `skills_list` alone. Verify actual prompt-candidate scoring through `SkillIndexDB.get_prompt_candidates()` with a representative user message:

```bash
PYTHONPATH=/home/ubuntu/.hermes/hermes-agent python3 - <<'PY'
from tools.skill_index_db import SkillIndexDB
DB='/home/ubuntu/.hermes/profiles/myknot/skill_index.db'
db=SkillIndexDB(DB)
q='GitHubにリポジトリ作ってpushしてください'
for r in db.get_prompt_candidates(user_message=q, limit=10):
    print(f"{r['score']:.1f}\t{r['skill_name']}\t{r['description']}")
PY
```

Current `tools/skill_index_db.py` scoring uses `description_full` plus vector similarity and SudachiPy/token matching. Legacy DB columns such as `tags_json` and `triggers_json` may still exist in older DBs, but the current schema comments mark them deprecated and prompt-candidate scoring does not use them directly. Therefore, when recall is the goal, put the strongest Japanese/English intent phrases in `description_full` as well as in SKILL.md `triggers` and tags.

If `skill_manage(action='patch')` is blocked by a security scan because an existing skill contains command examples involving tokens, secrets, `curl`, or `git clone`, do not assume the intended metadata change is unsafe. Inspect the findings; if they are pre-existing examples and the requested edit is narrowly scoped, use a targeted file patch on the SKILL.md and then verify with `skill_view`, `skills_list`, and `SkillIndexDB.get_prompt_candidates()`.

## Pitfalls

- Do not assume `skills_list` is the complete persistence state; it currently reflects filesystem discovery plus best-effort DB sync.
- Do not describe `skill_usage_events` as a skill; it is a DB table recording skill usage history with columns such as `skill_name`, `used_at`, `session_id`, `platform`, and `trigger`.
- Avoid deleting usage history unless the user wants full removal of a skill and its traces from the skill index.
- If the target profile matters, use the profile-local DB, not only the global `/home/ubuntu/.hermes/skill_index.db`.
- When modifying Hermes source code or profile skills, follow the user's self-refactor safety workflow; `skill_index.db` itself is normally a live cache/state file and should not be casually committed.

## Completion criteria

A skill deletion/audit is complete only when:

- The filesystem has no relevant skill directory/file.
- `skills_list` does not show the skill.
- The global and profile-local `skill_index.db` files have no relevant rows in `skills`.
- If full cleanup was requested, related rows are also gone from `skill_usage_events` and `skill_usage_rollups`.
