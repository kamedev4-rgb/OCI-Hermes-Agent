#!/usr/bin/env python3
"""MyCARE Docker monitor — LLM-free monitor + direct Discord notification."""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

WATCHED_CONTAINERS = ["myknot_postgres"]
DISCORD_API_BASE = "https://discord.com/api/v10"


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def get_container_status(name: str) -> str | None:
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}}", name],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def restart_container(name: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["docker", "start", name],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, ""
    return False, (result.stderr or result.stdout).strip()


def build_message(restarted: list[str], failed: list[str]) -> str:
    lines = [f"⚠️ MyCARE docker_monitor ({utc_now()})"]
    if restarted:
        lines.append(f"- restarted: {', '.join(restarted)}")
    if failed:
        lines.append("- failed:")
        lines.extend(f"  - {item}" for item in failed)
    return "\n".join(lines)


def send_discord_message(message: str) -> tuple[bool, str]:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    channel_id = os.getenv("DISCORD_MYCARE_CHANNEL_ID", "").strip()
    if not token or not channel_id:
        return False, "Missing DISCORD_BOT_TOKEN or DISCORD_MYCARE_CHANNEL_ID"

    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
        data=payload,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "mycare-docker-monitor/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if 200 <= resp.status < 300:
                return True, ""
            return False, f"Discord API returned HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        return False, f"Discord API HTTPError {exc.code}: {body}"
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"Discord send failed: {exc}"


if __name__ == "__main__":
    restarted: list[str] = []
    failed: list[str] = []
    already_running: list[str] = []

    for name in WATCHED_CONTAINERS:
        status = get_container_status(name)
        if status == "running":
            already_running.append(name)
        elif status is None:
            failed.append(f"{name}: container not found")
        else:
            ok, err = restart_container(name)
            if ok:
                restarted.append(name)
            else:
                failed.append(f"{name}: {err}")

    result = {
        "running": already_running,
        "restarted": restarted,
        "failed": failed,
        "action_taken": bool(restarted or failed),
        "notified": False,
    }

    if restarted or failed:
        message = build_message(restarted, failed)
        ok, err = send_discord_message(message)
        result["notified"] = ok
        if ok:
            result["message"] = message
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0 if not failed else 1)
        result["notify_error"] = err
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    print("[SILENT]")
    sys.exit(0)
