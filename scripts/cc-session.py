#!/usr/bin/env python3
"""
cc-session.py
Claude Codeとのセッションを管理する。
1トピック1セッション・タイムアウト2日。
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
SESSION_FILE = HERMES_HOME / "cc_session.json"
TIMEOUT_DAYS = 2


def load_session() -> dict | None:
    if not SESSION_FILE.exists():
        return None
    with open(SESSION_FILE) as f:
        return json.load(f)


def save_session(data: dict):
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f, indent=2)


def delete_session():
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def check():
    """セッション状態を確認して stdout に出力する。"""
    session = load_session()
    if not session:
        print("new")
        return

    timeout_at = datetime.fromisoformat(session["timeout_at"])
    now = datetime.now(timezone.utc)

    if now > timeout_at:
        delete_session()
        print("timeout")
    else:
        print(f"continue {session['session_id']}")


def start(topic: str, prompt: str):
    """新規セッションでClaude Codeを起動する。"""
    now = datetime.now(timezone.utc)
    timeout_at = now + timedelta(days=TIMEOUT_DAYS)

    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=300
    )

    # セッションIDをClaude Codeの出力から取得できないため、
    # claude --resume 用に最新セッションIDをsettingsから取得する
    session_id = _get_latest_session_id()

    session_data = {
        "session_id": session_id,
        "topic": topic,
        "created_at": now.isoformat(),
        "timeout_at": timeout_at.isoformat()
    }
    save_session(session_data)

    output = result.stdout.strip()
    print(output)


def continue_session(prompt: str):
    """既存セッションを継続してClaude Codeを呼び出す。"""
    session = load_session()
    if not session:
        print("ERROR: セッションが存在しません", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ["claude", "--resume", session["session_id"], "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=300
    )

    # timeout_atを更新（最終アクティビティから2日）
    now = datetime.now(timezone.utc)
    session["timeout_at"] = (now + timedelta(days=TIMEOUT_DAYS)).isoformat()
    save_session(session)

    output = result.stdout.strip()
    print(output)


def close():
    """セッションを明示的にクローズする。"""
    session = load_session()
    if session:
        topic = session.get("topic", "不明")
        delete_session()
        print(f"セッション '{topic}' をクローズしました。")
    else:
        print("アクティブなセッションはありません。")


def _get_latest_session_id() -> str:
    """~/.claude/projects から最新セッションIDを取得する。"""
    try:
        projects_dir = Path.home() / ".claude" / "projects"
        jsonl_files = sorted(projects_dir.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if jsonl_files:
            return jsonl_files[0].stem
    except Exception:
        pass
    return "unknown"


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("check")

    p_start = subparsers.add_parser("start")
    p_start.add_argument("topic")
    p_start.add_argument("prompt")

    p_continue = subparsers.add_parser("continue")
    p_continue.add_argument("prompt")

    subparsers.add_parser("close")

    args = parser.parse_args()

    if args.command == "check":
        check()
    elif args.command == "start":
        start(args.topic, args.prompt)
    elif args.command == "continue":
        continue_session(args.prompt)
    elif args.command == "close":
        close()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
