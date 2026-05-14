---
name: github-repo-publish-local-project
description: "ローカルprojectをGitHubへ安全publish"
description_full: "Use when kame-dev asks to create a GitHub repository for an existing local project and push the current code. Captures the safe workflow learned from publishing Clipping Note: verify GitHub auth, inspect local project state, add .gitignore before git init/add, exclude secrets/runtime artifacts, run lightweight validation, create private repo with gh, push, and verify remote/default branch."
version: 1.0.0
author: MyKNOT
metadata:
  hermes:
    tags: [github, git, publish, repo, secrets, devops]
triggers:
  - "GitHubにリポジトリ作ってpush"
  - "github repo create"
  - "create repository and push"
  - "ローカルプロジェクトをGitHubへ"
---

# GitHub Repo Publish Local Project

## When to use

Use this when publishing an existing local project directory to GitHub for kame-dev, especially when the directory was not already a git repository.

## Workflow

1. Locate the project directory from user context or prior skill/memory.
2. Check GitHub CLI auth first:

```bash
gh auth status
```

3. Inspect whether the target directory is already a git repo and whether it has remotes:

```bash
git -C /path/to/project status --short --branch
git -C /path/to/project remote -v
```

If this fails with `not a git repository`, treat it as an uninitialized project.

4. Before `git add`, inspect files and identify secrets/runtime/generated artifacts. Typical exclusions:

```gitignore
# Environment / secrets
.env
.env.*
!.env.example
secrets/

# Runtime data
storage/
*.sqlite
*.sqlite-*
*.db

# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Node / Next.js
node_modules/
.next/
out/
dist/
.turbo/
*.tsbuildinfo

# Logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# OS / editor
.DS_Store
.vscode/
.idea/
```

5. Add or update `.gitignore` before initializing/adding files. For projects with real browser profiles, auth cookies, uploaded files, local DBs, or build caches, verify they appear as ignored before commit:

```bash
git status --short --ignored | sed -n '1,160p'
```

Secrets/artifacts should show under `!!`, not `??` or `A`.

6. Run lightweight validation before publishing. Examples:

```bash
python3 -m compileall /path/to/project/apps/api/app
cd /path/to/project/apps/web && npm run build
```

If a build cache has ownership problems from Docker/root-owned files, fix that cache only after confirming the path is project-local and generated. Prefer changing ownership of the specific cache directory over deleting it.

7. Initialize git if needed, set a sane identity, stage, review staged names, then commit:

```bash
cd /path/to/project
git init -b main
git config user.name "kame-dev"
git config user.email "<safe noreply/local email>"
git add .
git status --short
git diff --cached --name-only | sed -n '1,200p'
git commit -m "Initial <Project Name> MVP"
```

Do not proceed if `.env`, `secrets/`, `storage/`, `node_modules/`, `.next/`, or `__pycache__/` are staged.

8. Check whether the desired repo already exists:

```bash
gh repo view OWNER/REPO --json nameWithOwner,visibility,url 2>/dev/null || true
```

9. Create a new private repo and push. Default to private unless the user explicitly requests public:

```bash
gh repo create REPO --private --source=. --remote=origin --push
```

10. Verify final state:

```bash
git status --short --branch
git remote -v
gh repo view OWNER/REPO --json nameWithOwner,visibility,url,defaultBranchRef
```

Expected clean result: branch tracks `origin/main`, repo URL exists, visibility is intended, default branch is `main`.

## Pitfalls

- Do not run `git add .` before creating `.gitignore`; it may stage `.env`, browser cookies, NotebookLM/Google auth state, upload storage, local DBs, or build outputs.
- `search_files` can reveal ignored/generated directories; if output is dominated by `secrets/`, `.next/`, or `node_modules/`, narrow checks and add `.gitignore` immediately.
- `gh auth status` may report missing `read:org`; for personal repos this is not necessarily blocking if `repo` scope is present.
- `git -C <dir> status` failing with `not a git repository` is expected for uninitialized local apps; initialize after ignore rules are in place.
- Build-cache ownership fixes should be limited to generated cache directories and never applied broadly to the project or home directory.

## Reporting

Final user report should include:

- GitHub repository URL
- visibility
- default branch
- pushed commit hash/message
- verification performed
- confirmation that secret/runtime/generated directories were ignored
