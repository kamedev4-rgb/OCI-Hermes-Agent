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
NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"


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
    api_key = os.getenv("NVIDIA_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return False, "Missing NVIDIA_API_KEY"

    prompt = f"""OCI監視アラートを日本語でDiscord用に簡潔にまとめてください。

現在時刻: {utc_now()}
監視データ:
- ディスク使用率: {payload.get('disk_pct')}%
- メモリ使用率: {payload.get('mem_pct')}%
- アラート数: {payload.get('alert_count')}
- アラート内容: {', '.join(payload.get('alerts', []))}

出力形式: Discordに送信する日本語テキストのみ。絵文字を使って見やすくしてください。"""

    body = json.dumps({
        "model": NVIDIA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{NVIDIA_API_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            text = result["choices"][0]["message"]["content"].strip()
            return True, text
    except urllib.error.HTTPError as exc:
        body_err = exc.read().decode("utf-8", errors="replace")[:300]
        return False, f"NVIDIA API HTTPError {exc.code}: {body_err}"
    except Exception as exc:
        return False, f"NVIDIA API failed: {exc}"


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
            f"- disk_pct: {payload.get('disk_pct')}%\n"
            f"- mem_pct: {payload.get('mem_pct')}%\n"
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
