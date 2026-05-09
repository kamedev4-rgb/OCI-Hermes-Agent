---
name: shared-notes-crud
description: "shared-notes CRUD"
description_full: "CRUD operations for kame-dev's shared-notes app using MyKNOT-friendly CLI/API/direct Markdown access. Use for creating, searching, reading, appending, rewriting, moving, and deleting notes while keeping Markdown files and SQLite/FTS metadata synchronized."
version: 1.0.1
author: MyKNOT
metadata:
  hermes:
    tags: [shared-notes, crud, notes, cli, sqlite, markdown, myknot]
triggers:
  - "shared-notes CRUD"
  - "共有メモ CRUD"
  - "シェアドノート"
  - "メモを作成"
  - "メモを検索"
  - "メモを読む"
  - "メモを追記"
  - "メモを削除"
---

# Shared Notes CRUD

## When to use

Use this skill when MyKNOT needs to create, search, read, update, append, rewrite, move, or delete notes in kame-dev's shared-notes app.

App path:

```bash
cd /home/ubuntu/saas/shared-notes
export DATA_DIR=/home/ubuntu/saas/shared-notes/data
```

Data layout:

```text
/home/ubuntu/saas/shared-notes/data/notes/*.md
/home/ubuntu/saas/shared-notes/data/shared-notes.sqlite
```

## Create

Preferred CLI:

```bash
printf '%s\n' '本文' | DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/create-note 'タイトル' --tags tag1,tag2
```

Options:

```bash
scripts/create-note <title> [--tag tag] [--tags a,b] [--slug slug] [--body text] [--folder folder/path]
```

The command prints JSON including `id`, `slug`, `title`, `file_path`, `tags`, and `updated_at`.

## Read

By ID or slug:

```bash
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/read-note <id-or-slug>
```

## Search

SQLite FTS search:

```bash
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/search-notes <query>
```

Notes:

- `scripts/search-notes` has fallback quoting for punctuation such as hyphens.
- Japanese FTS tokenization can miss terms that are visible in the note, especially katakana or mixed punctuation. If search gives no result, try a shorter word, another key phrase, tag, title fragment, or slug.
- For verification after an edit, always use `scripts/read-note` as the source of truth; search alone is not enough.

## Append vs rewrite

Append text:

```bash
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/append-note <id-or-slug> '追記本文'
```

Use append only when the user clearly wants additive history/logging.

If the user says a note is hard to read, stale, redundant, or appended sections are making it messy, do **not** append more. Rewrite/synthesize the full Markdown into a clean current-state note, preserving frontmatter identity/tags and syncing SQLite/FTS metadata.

## Structured update / full rewrite

For structured edits/removals, `scripts/append-note` is not enough. Use this workflow:

1. Find/read the note:
   ```bash
   DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/search-notes '<query>'
   DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/read-note <id-or-slug>
   ```
2. Rewrite or patch the Markdown file carefully. Preserve `id`, `slug`, `title`, `tags`, `folder_path`, and `created_at`; update only `updated_at` and body unless intentionally changing metadata.
3. Re-sync SQLite:
   - `notes.excerpt`: whitespace-normalized body, first ~180 chars
   - `notes.content_hash`: SHA-256 of the complete raw Markdown file
   - `notes.updated_at`: same as frontmatter
   - `note_fts`: delete existing row for note_id, insert current title/body/tags
4. Verify with `scripts/read-note <id-or-slug>` and at least one `scripts/search-notes '<changed phrase>'` query. If Japanese search misses a visible term, verify with a different phrase and rely on `read-note`.

Direct Markdown edits alone leave search/list metadata stale.

## Delete

Preferred CLI soft-delete:

```bash
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/delete-note <id-or-slug>
```

For non-interactive/test use, add `--yes`:

```bash
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/delete-note <id-or-slug> --yes
```

Deletion is soft-delete in SQLite (`deleted_at` is set) and a history snapshot is stored before deletion. The Markdown file remains on disk for recovery/history.

## Tags

List tags:

```bash
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/list-tags
```

## Folders

Folder hierarchy is represented by each note's `folder_path` string plus a lightweight `folders` table so empty folders can exist. Empty `folder_path` means the root folder (`ルート` in UI), not “uncategorized”. Use plain text / Material Symbols in UI examples; do not use emoji.

Folder-aware CLI:

```bash
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/create-note 'タイトル' --folder Projects/shared-notes
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/search-notes '<query>' --folder Projects/shared-notes
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/list-notes [--folder Projects/shared-notes] [--json]
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/list-folders [--json]
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/create-folder Projects/shared-notes
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/rename-folder Projects/shared-notes Projects/shared-notes-v2
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/delete-folder Projects/shared-notes
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/move-note <id-or-slug> Projects/shared-notes
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/move-note <id-or-slug> /
```

Folder-aware scripts must keep Markdown frontmatter and SQLite synchronized. `move-note`, `rename-folder`, and `delete-folder` update `folder_path` in both places. `list-folders --json` and `list-notes --json` are useful for MyKNOT because they avoid parsing UI text. Deleting a folder is allowed even with child folders/notes; affected notes are moved to root rather than deleted.

## Verification checklist

After creating/updating/deleting:

1. Search for the title or key phrase with `scripts/search-notes`.
2. Read the note with `scripts/read-note` when it should exist.
3. For deletion, confirm search no longer returns the note and `read-note <id>` returns `not found`.
4. If UI availability matters, open `http://127.0.0.1:3000` or Tailnet URL and confirm visually.

## Pitfalls

- Always set `DATA_DIR=/home/ubuntu/saas/shared-notes/data` for host-side CLI use.
- After creating a note from stdin or file redirection, immediately verify with `scripts/read-note`. In one observed case, `scripts/create-note 'title' --tags ... < file.md` created only frontmatter with an empty body; fix by appending the intended Markdown with `scripts/append-note <id-or-slug> '<body>'` or use a creation path that explicitly passes body content, then verify search/read again.
- The Docker Compose app should run with host `ubuntu` UID/GID (`1001:1001`) and `./data` should be owned by that user. If API/container-created files become root-owned, host CLI operations such as `scripts/delete-note` can fail with EACCES; fix ownership before retrying.
- Do not create notes by writing Markdown files only; SQLite metadata/FTS/tags/links must also be updated.
- Slugs must be unique across all notes, including soft-deleted rows.
- Delete notes with `scripts/delete-note` rather than hard-deleting Markdown files or using the API directly.
- User explicitly cares whether CRUD actions used CLI vs API; report accurately and do not call an API deletion a CLI deletion.
