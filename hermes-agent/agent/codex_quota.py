"""Codex quota capture, persistence, and monitoring helpers."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from hermes_constants import get_default_hermes_root

JST = ZoneInfo("Asia/Tokyo")
THRESHOLDS = (85, 90, 95)
STATE_VERSION = 1


def get_global_dir(root: Path | None = None) -> Path:
    return (root or get_default_hermes_root()) / "global"



def get_state_path(root: Path | None = None) -> Path:
    return get_global_dir(root) / "state" / "codex_quota_state.json"



def get_config_path(root: Path | None = None) -> Path:
    return get_global_dir(root) / "config" / "codex_quota_monitor.json"



def _mkdir_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)



def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _mkdir_parent(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)



def load_state(path: Path | None = None) -> dict[str, Any]:
    state_path = path or get_state_path()
    if not state_path.exists():
        return {"version": STATE_VERSION, "accounts": {}}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": STATE_VERSION, "accounts": {}}
    if not isinstance(payload, dict):
        return {"version": STATE_VERSION, "accounts": {}}
    payload.setdefault("version", STATE_VERSION)
    payload.setdefault("accounts", {})
    if not isinstance(payload["accounts"], dict):
        payload["accounts"] = {}
    return payload



def save_state(state: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    state_path = path or get_state_path()
    _atomic_write_json(state_path, state)
    return state



def _pad_b64(value: str) -> str:
    return value + "=" * ((4 - (len(value) % 4)) % 4)



def decode_access_token(access_token: str) -> dict[str, Any]:
    if not isinstance(access_token, str) or access_token.count(".") < 2:
        return {}
    try:
        payload = access_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(_pad_b64(payload)).decode("utf-8"))
    except Exception:
        return {}



def account_identity(access_token: str) -> dict[str, Any]:
    payload = decode_access_token(access_token)
    auth = payload.get("https://api.openai.com/auth") or {}
    profile = payload.get("https://api.openai.com/profile") or {}
    account_id = auth.get("chatgpt_account_id")
    user_id = auth.get("chatgpt_user_id") or auth.get("user_id")
    sub = payload.get("sub")
    email = profile.get("email")
    if isinstance(account_id, str) and account_id.strip():
        account_key = account_id.strip()
    elif isinstance(sub, str) and sub.strip():
        account_key = sub.strip()
    elif isinstance(email, str) and email.strip():
        account_key = email.strip().lower()
    else:
        account_key = hashlib.sha256(access_token.encode("utf-8")).hexdigest()[:16]
    return {
        "account_key": account_key,
        "account_id": account_id,
        "user_id": user_id,
        "sub": sub,
        "email": email,
        "plan_type": auth.get("chatgpt_plan_type"),
    }



def _header_lookup(headers: dict[str, Any], key: str) -> str:
    for k, value in headers.items():
        if str(k).lower() == key.lower():
            return "" if value is None else str(value)
    return ""



def _safe_int(value: Any) -> int | None:
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except Exception:
        return None



def snapshot_from_headers(
    headers: dict[str, Any],
    *,
    access_token: str,
    observed_at: int | float | None = None,
    source: str | None = None,
) -> dict[str, Any] | None:
    five_hour_used = _safe_int(_header_lookup(headers, "x-codex-primary-used-percent"))
    week_used = _safe_int(_header_lookup(headers, "x-codex-secondary-used-percent"))
    five_hour_reset_at = _safe_int(_header_lookup(headers, "x-codex-primary-reset-at"))
    week_reset_at = _safe_int(_header_lookup(headers, "x-codex-secondary-reset-at"))
    if None in (five_hour_used, week_used, five_hour_reset_at, week_reset_at):
        return None

    ident = account_identity(access_token)
    now_ts = int(observed_at if observed_at is not None else time.time())
    return {
        **ident,
        "five_hour_used_pct": five_hour_used,
        "week_used_pct": week_used,
        "five_hour_reset_at": five_hour_reset_at,
        "week_reset_at": week_reset_at,
        "observed_at": now_ts,
        "source": source or "",
        "active_limit": _header_lookup(headers, "x-codex-active-limit") or None,
        "header_plan_type": _header_lookup(headers, "x-codex-plan-type") or None,
    }



def _normalize_notified(values: Any) -> list[int]:
    if not isinstance(values, list):
        return []
    out: list[int] = []
    for value in values:
        iv = _safe_int(value)
        if iv is not None and iv not in out:
            out.append(iv)
    out.sort()
    return out



def update_state_with_snapshot(state: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    state = dict(state or {})
    accounts = dict(state.get("accounts") or {})
    account_key = snapshot["account_key"]
    current = dict(accounts.get(account_key) or {})
    latest = current.get("latest") or {}
    notified = dict(current.get("notified") or {})
    notified_5h = _normalize_notified(notified.get("5h"))
    notified_week = _normalize_notified(notified.get("week"))

    if latest.get("five_hour_reset_at") != snapshot.get("five_hour_reset_at"):
        notified_5h = []
    if latest.get("week_reset_at") != snapshot.get("week_reset_at"):
        notified_week = []

    current["account"] = {
        key: snapshot.get(key)
        for key in ("account_key", "account_id", "user_id", "sub", "email", "plan_type", "header_plan_type", "active_limit")
    }
    current["latest"] = snapshot
    current["notified"] = {"5h": notified_5h, "week": notified_week}
    current["updated_at"] = snapshot.get("observed_at")
    accounts[account_key] = current
    state["version"] = STATE_VERSION
    state["accounts"] = accounts
    return state



def due_thresholds(account_state: dict[str, Any], thresholds: tuple[int, ...] = THRESHOLDS) -> dict[str, list[int]]:
    latest = account_state.get("latest") or {}
    notified = account_state.get("notified") or {}
    used_5h = _safe_int(latest.get("five_hour_used_pct")) or 0
    used_week = _safe_int(latest.get("week_used_pct")) or 0
    notified_5h = set(_normalize_notified(notified.get("5h")))
    notified_week = set(_normalize_notified(notified.get("week")))
    return {
        "5h": [level for level in thresholds if used_5h >= level and level not in notified_5h],
        "week": [level for level in thresholds if used_week >= level and level not in notified_week],
    }



def mark_notified(account_state: dict[str, Any], due: dict[str, list[int]]) -> dict[str, Any]:
    state = dict(account_state)
    notified = dict(state.get("notified") or {})
    for key in ("5h", "week"):
        current = set(_normalize_notified(notified.get(key)))
        current.update(_normalize_notified(due.get(key)))
        notified[key] = sorted(current)
    state["notified"] = notified
    return state



def persist_codex_headers(
    headers: dict[str, Any],
    *,
    access_token: str,
    observed_at: int | float | None = None,
    source: str | None = None,
    state_path: Path | None = None,
) -> dict[str, Any] | None:
    snapshot = snapshot_from_headers(headers, access_token=access_token, observed_at=observed_at, source=source)
    if snapshot is None:
        return None
    state = load_state(state_path)
    updated = update_state_with_snapshot(state, snapshot)
    return save_state(updated, state_path)



def _message_event_config(config: dict[str, Any]) -> dict[str, Any]:
    event_cfg = config.get("message_event") or {}
    if not isinstance(event_cfg, dict):
        event_cfg = {}
    event_cfg.setdefault("enabled", True)
    event_cfg.setdefault("thresholds", list(config.get("thresholds", THRESHOLDS)))
    delivery = config.get("delivery") or {}
    event_cfg.setdefault("discord_channel_id", str(event_cfg.get("discord_channel_id") or delivery.get("discord_channel_id") or "").strip())
    return event_cfg



def process_codex_headers(
    headers: dict[str, Any],
    *,
    access_token: str,
    observed_at: int | float | None = None,
    source: str | None = None,
    root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    hermes_root = root or get_default_hermes_root()
    snapshot = snapshot_from_headers(headers, access_token=access_token, observed_at=observed_at, source=source)
    if snapshot is None:
        return None

    state_path = get_state_path(hermes_root)
    state = load_state(state_path)
    state = update_state_with_snapshot(state, snapshot)
    config = load_monitor_config(hermes_root)
    event_cfg = _message_event_config(config)
    threshold_sent = False
    due = {"5h": [], "week": []}

    if event_cfg.get("enabled"):
        account_key = snapshot["account_key"]
        account_state = state["accounts"][account_key]
        due = due_thresholds(account_state, thresholds=tuple(int(v) for v in event_cfg.get("thresholds", THRESHOLDS)))
        if due["5h"] or due["week"]:
            bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
            channel_id = str(event_cfg.get("discord_channel_id") or "").strip()
            send_discord_message(format_notification(snapshot, now=now), channel_id=channel_id, bot_token=bot_token)
            state["accounts"][account_key] = mark_notified(account_state, due)
            threshold_sent = True

    save_state(state, state_path)
    return {
        "snapshot": snapshot,
        "state_path": str(state_path),
        "threshold_notification_sent": threshold_sent,
        "due": due,
    }



def _format_hhmm_jst(unix_ts: int) -> str:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).astimezone(JST).strftime("%H:%M")



def _format_week_remaining(reset_unix_ts: int, now: datetime | None = None) -> str:
    now_jst = now.astimezone(JST) if now is not None else datetime.now(JST)
    reset_jst = datetime.fromtimestamp(reset_unix_ts, tz=timezone.utc).astimezone(JST)
    total = max(0, int((reset_jst - now_jst).total_seconds()))
    days = total // 86400
    hours = (total % 86400) // 3600
    minutes = (total % 3600) // 60
    return f"{days}d {hours:02d}:{minutes:02d}"



def format_notification(snapshot: dict[str, Any], now: datetime | None = None) -> str:
    return (
        f"5h: {snapshot['five_hour_used_pct']}% used / reset {_format_hhmm_jst(snapshot['five_hour_reset_at'])}\n"
        f"week: {snapshot['week_used_pct']}% used / reset {_format_week_remaining(snapshot['week_reset_at'], now=now)}"
    )



def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}



def _parse_last_refresh(text: str | None) -> float:
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0



def iter_codex_auth_entries(root: Path | None = None) -> list[dict[str, Any]]:
    hermes_root = root or get_default_hermes_root()
    auth_paths = [hermes_root / "auth.json"]
    profiles_dir = hermes_root / "profiles"
    if profiles_dir.is_dir():
        auth_paths.extend(sorted(p / "auth.json" for p in profiles_dir.iterdir() if (p / "auth.json").exists()))

    entries: list[dict[str, Any]] = []
    seen_tokens: set[str] = set()
    for auth_path in auth_paths:
        payload = _load_json(auth_path)
        pool = payload.get("credential_pool") or {}
        candidates = list(pool.get("openai-codex") or [])
        provider_tokens = ((payload.get("providers") or {}).get("openai-codex") or {}).get("tokens") or {}
        if provider_tokens.get("access_token"):
            candidates.append(
                {
                    "access_token": provider_tokens.get("access_token"),
                    "refresh_token": provider_tokens.get("refresh_token"),
                    "last_refresh": ((payload.get("providers") or {}).get("openai-codex") or {}).get("last_refresh"),
                    "source": "providers.openai-codex.tokens",
                }
            )
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            token = entry.get("access_token")
            if not isinstance(token, str) or not token.strip() or token in seen_tokens:
                continue
            seen_tokens.add(token)
            ident = account_identity(token)
            entries.append(
                {
                    **ident,
                    "access_token": token,
                    "refresh_token": entry.get("refresh_token"),
                    "last_refresh": entry.get("last_refresh"),
                    "last_refresh_ts": _parse_last_refresh(entry.get("last_refresh")),
                    "auth_path": str(auth_path),
                }
            )
    return entries



def pick_probe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = entry["account_key"]
        current = best.get(key)
        if current is None or entry.get("last_refresh_ts", 0.0) > current.get("last_refresh_ts", 0.0):
            best[key] = entry
    return list(best.values())



def live_probe_codex_quota(
    access_token: str,
    *,
    source: str | None = None,
    model: str = "gpt-5.4-mini",
    timeout: int = 60,
) -> dict[str, Any]:
    url = "https://chatgpt.com/backend-api/codex/responses"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "instructions": "Reply with OK only.",
        "input": [{"role": "user", "content": "ping"}],
        "store": False,
        "stream": True,
    }
    with requests.post(url, headers=headers, json=payload, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        snapshot = snapshot_from_headers(dict(response.headers), access_token=access_token, observed_at=time.time(), source=source)
        if snapshot is None:
            raise RuntimeError("Codex quota headers were missing from live probe response.")
        for idx, _line in enumerate(response.iter_lines()):
            if idx >= 4:
                break
        return snapshot



def load_monitor_config(root: Path | None = None) -> dict[str, Any]:
    config_path = get_config_path(root)
    payload = _load_json(config_path)
    payload.setdefault("delivery", {})
    payload.setdefault("probe_model", "gpt-5.4-mini")
    payload.setdefault("thresholds", list(THRESHOLDS))
    payload.setdefault("mode", "always")
    payload.setdefault("message_event", {})
    return payload



def send_discord_message(message: str, *, channel_id: str, bot_token: str, timeout: int = 30) -> None:
    if not channel_id or not bot_token:
        raise RuntimeError("Discord delivery requires channel_id and bot token.")
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    response = requests.post(
        url,
        headers={"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"},
        json={"content": message},
        timeout=timeout,
    )
    response.raise_for_status()



def run_monitor(*, root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    hermes_root = root or get_default_hermes_root()
    state = load_state(get_state_path(hermes_root))
    config = load_monitor_config(hermes_root)
    entries = pick_probe_entries(iter_codex_auth_entries(hermes_root))
    notifications: list[dict[str, Any]] = []
    mode = str(config.get("mode") or "always").strip().lower()

    for entry in entries:
        snapshot = live_probe_codex_quota(
            entry["access_token"],
            source=entry.get("auth_path"),
            model=str(config.get("probe_model") or "gpt-5.4-mini"),
        )
        state = update_state_with_snapshot(state, snapshot)
        account_key = snapshot["account_key"]
        account_state = state["accounts"][account_key]
        if mode == "thresholds":
            due = due_thresholds(account_state, thresholds=tuple(int(v) for v in config.get("thresholds", THRESHOLDS)))
            if due["5h"] or due["week"]:
                notifications.append({"account_key": account_key, "message": format_notification(snapshot, now=now), "due": due})
        else:
            notifications.append({"account_key": account_key, "message": format_notification(snapshot, now=now), "due": {"5h": [], "week": []}})

    delivery = config.get("delivery") or {}
    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    channel_id = str(delivery.get("discord_channel_id") or "").strip()
    sent = []
    for item in notifications:
        send_discord_message(item["message"], channel_id=channel_id, bot_token=bot_token)
        account_key = item["account_key"]
        if mode == "thresholds":
            state["accounts"][account_key] = mark_notified(state["accounts"][account_key], item["due"])
        sent.append(item["message"])

    save_state(state, get_state_path(hermes_root))
    return {
        "accounts": len(entries),
        "notifications": sent,
        "silent": not sent,
        "state_path": str(get_state_path(hermes_root)),
        "mode": mode,
    }



def main() -> int:
    try:
        result = run_monitor()
        if result["silent"]:
            print("[SILENT]")
        else:
            print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
