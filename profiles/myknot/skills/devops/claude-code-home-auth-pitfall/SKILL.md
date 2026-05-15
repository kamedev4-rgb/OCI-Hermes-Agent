---
name: claude-code-home-auth-pitfall
description: Claude Code HOME認証問題
description_full: MyKNOT/Hermes profile-local HOME環境でClaude Codeやcc-session.pyがNot logged inになる問題を切り分け、HOME=/home/ubuntuを明示して回避する手順。delegate_task子エージェントからClaude Codeを呼ぶ場合にも適用する。
triggers:
  - Claude Code Not logged in
  - claude code 未ログイン
  - delegate_task claude code
  - cc-session Not logged in
  - HOME=/home/ubuntu claude
---

# Claude Code HOME/Auth Pitfall

## When to use

Use this when Claude Code or `cc-session.py` reports:

```text
Not logged in · Please run /login
```

inside MyKNOT/Hermes, especially from `delegate_task` child agents.

## Cause

MyKNOT profile execution may use profile-local HOME:

```text
HOME=/home/ubuntu/.hermes/profiles/myknot/home
HERMES_HOME=/home/ubuntu/.hermes/profiles/myknot
```

but Claude Code OAuth credentials are under the real Ubuntu home:

```text
/home/ubuntu/.claude
/home/ubuntu/.claude.json
```

So Claude Code looks in the wrong HOME and reports Not logged in.

## Verification

```bash
echo "$HOME"
which claude
claude --version
claude -p 'Say OK only' --output-format text
HOME=/home/ubuntu claude -p 'Say OK only' --output-format text
```

Expected: the first `claude -p` may fail with `Not logged in`, while the `HOME=/home/ubuntu` version returns `OK`.

## Workaround

For direct Claude Code calls:

```bash
HOME=/home/ubuntu claude -p 'Say OK only' --output-format text
```

For `cc-session.py`:

```bash
HOME=/home/ubuntu HERMES_HOME=/home/ubuntu/.hermes/profiles/myknot \
  python3 /home/ubuntu/.hermes/scripts/cc-session.py start 'task prompt'
```

For `delegate_task` child agents, explicitly instruct the child to prefix Claude Code commands with:

```bash
HOME=/home/ubuntu
```

## ACP caveat

In the checked environment, Claude Code v2.1.119 did not support:

```bash
claude --acp --stdio
```

It returned `unknown option '--acp'`. Do not assume `delegate_task(acp_command="claude", acp_args=["--acp", "--stdio"])` works without verifying the installed CLI.

## Preferred permanent fix

Prefer setting HOME only for Claude Code invocation rather than copying credentials into the profile-local home, to avoid credential duplication and drift.
