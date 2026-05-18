#!/usr/bin/env python3
"""
cc-unblock.py
リセット時刻到達時に使用率を再確認し、フラグを解除する。
Cron から --kind weekly または --kind session で呼ばれる。
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
CC_STATUS = HERMES_HOME / "cc_status.json"
PREFILL = HERMES_HOME / "profiles/myknot/prefill-short-response.json"
CREDENTIALS = Path.home() / ".claude/.credentials.json"
CRON_DIR = HERMES_HOME / "profiles/myknot/cron"

WEEKLY_THRESHOLD = 70
SESSION_THRESHOLD = 90

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
    with open(CC_STATUS) as f:
        return json.load(f)


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
    try:
        subprocess.run(
            ["hermes", "chat", "-Q", "-q", message],
            env={**os.environ, "HERMES_HOME": str(HERMES_HOME)},
            timeout=30,
            check=False
        )
    except Exception as e:
        print(f"Discord通知失敗: {e}", file=sys.stderr)


def to_iso(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
    return val


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["weekly", "session"], required=True)
    args = parser.parse_args()

    try:
        usage = fetch_usage()
    except Exception as e:
        print(f"使用率取得失敗: {e}", file=sys.stderr)
        sys.exit(1)

    status = load_status()

    if args.kind == "weekly":
        pct = usage.get("seven_day", {}).get("utilization", 0) or 0
        reset = to_iso(usage.get("seven_day", {}).get("resets_at"))
        threshold = WEEKLY_THRESHOLD
        label = "週次"
    else:
        pct = usage.get("five_hour", {}).get("utilization", 0) or 0
        reset = to_iso(usage.get("five_hour", {}).get("resets_at"))
        threshold = SESSION_THRESHOLD
        label = "5時間"

    if pct < threshold:
        # 解除
        status[args.kind]["available"] = True
        status[args.kind]["unblock_at"] = None
        save_status(status)
        cc_available = status["weekly"]["available"] and status["session"]["available"]
        update_prefill(cc_available)
        notify_discord(f"Claude Code {label}制限が解除されました。委譲を再開します。")
        print(f"{args.kind} 解除完了 ({pct:.1f}%)")
    else:
        # まだ超過中 → 新しいresets_atでCronを再登録
        status[args.kind]["unblock_at"] = reset
        save_status(status)
        if reset:
            register_unblock_cron(reset, args.kind)
        print(f"{args.kind} まだ超過中 ({pct:.1f}%) → {reset} に再スケジュール")


if __name__ == "__main__":
    main()
