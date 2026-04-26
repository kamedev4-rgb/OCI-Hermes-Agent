#!/usr/bin/env python3
"""MyCARE OCI monitor runner — LLM only when detector exits 1."""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

DISCORD_API_BASE = "https://discord.com/api/v10"
PROFILE = "mycare"
DETECTOR = "/home/ubuntu/.hermes/profiles/mycare/scripts/oci_monitor.py"


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


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
            "User-Agent": "mycare-oci-monitor/1.0",
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
    except Exception as exc:
        return False, f"Discord send failed: {exc}"


def summarize_with_llm(payload: dict) -> tuple[bool, str]:
    prompt = f'''You are summarizing an OCI monitoring alert for Discord.

Current time: {utc_now()}
Monitoring payload:
```json
{json.dumps(payload, ensure_ascii=False)}
```

Task:
- Write a concise Japanese alert message for Discord.
- Include disk and memory percentages if present.
- Include each alert item clearly.
- Do not use tools.
- Output only the final message text.
'''
    result = subprocess.run(
        ["hermes", "--profile", PROFILE, "chat", "-Q", "-q", prompt],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout).strip()
        return False, f"Hermes summary failed: {stderr[:500]}"
    text = (result.stdout or "").strip()
    if not text:
        return False, "Hermes summary returned empty output"
    return True, text


if __name__ == "__main__":
    detector = subprocess.run(["python3", DETECTOR], capture_output=True, text=True, timeout=60)

    if detector.returncode == 0:
        sys.exit(0)

    if detector.returncode != 1:
        message = (
            f"⚠️ MyCARE oci_monitor runner error ({utc_now()})\n"
            f"- detector exit code: {detector.returncode}\n"
            f"- stderr: {(detector.stderr or '').strip()[:400]}"
        )
        ok, err = send_discord_message(message)
        if ok:
            sys.exit(1)
        print(err, file=sys.stderr)
        sys.exit(1)

    raw = (detector.stdout or "").strip()
    if not raw:
        print("oci_monitor exited 1 without payload", file=sys.stderr)
        sys.exit(1)

    try:
        payload = json.loads(raw)
    except Exception as exc:
        print(f"Invalid JSON from oci_monitor: {exc}", file=sys.stderr)
        sys.exit(1)

    ok, summary = summarize_with_llm(payload)
    if not ok:
        fallback = (
            f"⚠️ MyCARE OCI alert ({utc_now()})\n"
            f"- disk_pct: {payload.get('disk_pct')}\n"
            f"- mem_pct: {payload.get('mem_pct')}\n"
            + "\n".join(f"- {item}" for item in payload.get("alerts", []))
            + f"\n- summary_error: {summary}"
        )
        send_ok, err = send_discord_message(fallback)
        if send_ok:
            sys.exit(1)
        print(err, file=sys.stderr)
        sys.exit(1)

    send_ok, err = send_discord_message(summary)
    if not send_ok:
        print(err, file=sys.stderr)
        sys.exit(1)
    sys.exit(1)
