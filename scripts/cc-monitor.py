#!/usr/bin/env python3
"""
cc-monitor.py
Claude Code 使用率を定期チェックし、cc_status.json と prefill を更新する。
Cron: 毎時実行
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
CC_STATUS = HERMES_HOME / "cc_status.json"
PREFILL = HERMES_HOME / "profiles/myknot/prefill-short-response.json"
CREDENTIALS = Path.home() / ".claude/.credentials.json"
CRON_DIR = HERMES_HOME / "profiles/myknot/cron"

WEEKLY_THRESHOLD = 70
SESSION_THRESHOLD = 90  # 100%到達前に遮断

PREFILL_STATIC = [
    {
        "role": "system",
        "content": "回答は短く答えられるときは短く回答して、必要な情報だけを残し、文字数を減らす工夫をしてください。"
    },
    {
        "role": "system",
        "content": "意図・背景・暗黙知の整理が必要な場合は必ずClaude Codeに委譲してください。ジャンルは問いません。cc_availableはClaude Codeへの委譲が可能かを示します。"
    }
]


def get_access_token() -> str:
    with open(CREDENTIALS) as f:
        creds = json.load(f)
    return creds["claudeAiOauth"]["accessToken"]


def fetch_usage() -> dict:
    token = get_access_token()
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
        }
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def load_status() -> dict:
    if CC_STATUS.exists():
        with open(CC_STATUS) as f:
            return json.load(f)
    return {
        "weekly": {"available": True, "unblock_at": None},
        "session": {"available": True, "unblock_at": None}
    }


def save_status(status: dict):
    with open(CC_STATUS, "w") as f:
        json.dump(status, f, indent=2)


def update_prefill(cc_available: bool):
    prefill = PREFILL_STATIC + [
        {
            "role": "system",
            "content": f"cc_available: {'true' if cc_available else 'false'}"
        }
    ]
    with open(PREFILL, "w") as f:
        json.dump(prefill, f, indent=2, ensure_ascii=False)


def register_unblock_cron(unblock_at: str, kind: str):
    """unblock_at 時刻に cc-unblock.py を1回だけ実行するCronを登録する。"""
    dt = datetime.fromisoformat(unblock_at.replace("Z", "+00:00"))
    cron_entry = {
        "schedule": f"{dt.minute} {dt.hour} {dt.day} {dt.month} *",
        "command": f"python3 {HERMES_HOME}/scripts/cc-unblock.py --kind {kind}",
        "one_shot": True,
        "description": f"cc-unblock ({kind}) at {unblock_at}"
    }
    cron_file = CRON_DIR / f"cc_unblock_{kind}.json"
    with open(cron_file, "w") as f:
        json.dump(cron_entry, f, indent=2)


def notify_discord(message: str):
    """hermes CLI経由でDiscord通知を送る。"""
    try:
        subprocess.run(
            ["hermes", "chat", "-Q", "-q", message],
            env={**os.environ, "HERMES_HOME": str(HERMES_HOME)},
            timeout=30,
            check=False
        )
    except Exception as e:
        print(f"Discord通知失敗: {e}", file=sys.stderr)


def main():
    try:
        usage = fetch_usage()
    except Exception as e:
        print(f"使用率取得失敗: {e}", file=sys.stderr)
        sys.exit(1)

    weekly_pct = usage.get("seven_day", {}).get("utilization", 0) or 0
    session_pct = usage.get("five_hour", {}).get("utilization", 0) or 0
    weekly_reset = usage.get("seven_day", {}).get("resets_at")
    session_reset = usage.get("five_hour", {}).get("resets_at")

    # resets_atがエポック秒の場合はISO変換
    def to_iso(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
        return val

    weekly_reset = to_iso(weekly_reset)
    session_reset = to_iso(session_reset)

    status = load_status()
    changed = False

    # weekly チェック
    if weekly_pct >= WEEKLY_THRESHOLD:
        if status["weekly"]["available"]:
            status["weekly"]["available"] = False
            status["weekly"]["unblock_at"] = weekly_reset
            changed = True
            if weekly_reset:
                register_unblock_cron(weekly_reset, "weekly")
            notify_discord(
                f"Claude Code週次使用率が{weekly_pct:.1f}%に達しました。"
                f"委譲を停止します。復活予定: {weekly_reset}"
            )
    else:
        if not status["weekly"]["available"]:
            status["weekly"]["available"] = True
            status["weekly"]["unblock_at"] = None
            changed = True
            notify_discord("Claude Code週次使用率が70%未満に回復しました。委譲を再開します。")

    # session チェック
    if session_pct >= SESSION_THRESHOLD:
        if status["session"]["available"]:
            status["session"]["available"] = False
            status["session"]["unblock_at"] = session_reset
            changed = True
            if session_reset:
                register_unblock_cron(session_reset, "session")
            notify_discord(
                f"Claude Code5時間使用率が{session_pct:.1f}%に達しました。"
                f"委譲を停止します。復活予定: {session_reset}"
            )
    else:
        if not status["session"]["available"]:
            status["session"]["available"] = True
            status["session"]["unblock_at"] = None
            changed = True
            notify_discord("Claude Code5時間ブロックが回復しました。委譲を再開します。")

    if changed:
        save_status(status)

    # prefill は常に最新状態で上書き
    cc_available = status["weekly"]["available"] and status["session"]["available"]
    update_prefill(cc_available)

    print(f"weekly: {weekly_pct:.1f}% | session: {session_pct:.1f}% | cc_available: {cc_available}")


if __name__ == "__main__":
    main()
