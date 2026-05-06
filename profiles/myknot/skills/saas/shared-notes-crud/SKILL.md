---
name: shared-notes-crud
description: "CRUD operations for kame-dev's shared-notes app using MyKNOT-friendly CLI/API/direct Markdown access."
version: 1.0.0
author: MyKNOT
metadata:
  hermes:
    tags: [shared-notes, crud, notes, cli, sqlite, markdown, myknot]
triggers:
  - "shared-notes CRUD"
  - "共有メモ CRUD"
  - "メモを作成"
  - "メモを検索"
  - "メモを読む"
  - "メモを追記"
  - "メモを削除"
---

# Shared Notes CRUD

## When to use

Use this skill when MyKNOT needs to create, search, read, update, append, or delete notes in kame-dev's shared-notes app.

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
scripts/create-note <title> [--tag tag] [--tags a,b] [--slug slug] [--body text]
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
- If a query gives no result, try a shorter word, tag, title fragment, or slug.

## Update / Append

Append text:

```bash
DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/append-note <id-or-slug> '追記本文'
```

For structured edits/removals (for example, deleting an unnecessary section while adding a new TODO), `scripts/append-note` is not enough. Use this workflow:

1. Find/read the note:
   ```bash
   DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/search-notes '<query>'
   DATA_DIR=/home/ubuntu/saas/shared-notes/data scripts/read-note <id-or-slug>
   ```
2. Patch the Markdown file carefully.
3. Re-sync frontmatter `updated_at`, `notes.excerpt`, `notes.content_hash`, and `note_fts` in SQLite. Direct Markdown edits alone leave search/list metadata stale.
4. Verify with both `scripts/search-notes '<changed phrase>'` and `scripts/read-note <id-or-slug>`.

Prefer the app API or existing scripts when possible because they handle SQLite synchronization automatically.

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
- The Docker Compose app should run with host `ubuntu` UID/GID (`1001:1001`) and `./data` should be owned by that user. If API/container-created files become root-owned, host CLI operations such as `scripts/delete-note` can fail with EACCES; fix ownership before retrying.
- Do not create notes by writing Markdown files only; SQLite metadata/FTS/tags/links must also be updated.
- Slugs must be unique across all notes, including soft-deleted rows.
- Delete notes with `scripts/delete-note` rather than hard-deleting Markdown files or using the API directly.
- User explicitly cares whether CRUD actions used CLI vs API; report accurately and do not call an API deletion a CLI deletion.
