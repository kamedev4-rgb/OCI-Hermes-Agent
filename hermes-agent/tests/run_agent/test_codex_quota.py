from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from agent import codex_quota


def _fake_jwt(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}

    def _b64(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{_b64(header)}.{_b64(payload)}.sig"


def test_snapshot_from_headers_extracts_identity_and_usage():
    token = _fake_jwt(
        {
            "sub": "google-oauth2|1234567890",
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "acct-123",
                "chatgpt_user_id": "user-123",
                "chatgpt_plan_type": "plus",
            },
            "https://api.openai.com/profile": {"email": "user@example.com"},
        }
    )

    snapshot = codex_quota.snapshot_from_headers(
        {
            "x-codex-primary-used-percent": "12",
            "x-codex-secondary-used-percent": "66",
            "x-codex-primary-reset-at": "1777005338",
            "x-codex-secondary-reset-at": "1777400433",
            "x-codex-plan-type": "plus",
            "x-codex-active-limit": "premium",
        },
        access_token=token,
        observed_at=1776988344,
        source="profile:myknot",
    )

    assert snapshot["account_key"] == "acct-123"
    assert snapshot["account_id"] == "acct-123"
    assert snapshot["email"] == "user@example.com"
    assert snapshot["five_hour_used_pct"] == 12
    assert snapshot["week_used_pct"] == 66
    assert snapshot["five_hour_reset_at"] == 1777005338
    assert snapshot["week_reset_at"] == 1777400433
    assert snapshot["source"] == "profile:myknot"


def test_persist_codex_headers_writes_global_state_from_profile_home(tmp_path, monkeypatch):
    profile_home = tmp_path / "profiles" / "myknot"
    profile_home.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(profile_home))

    token = _fake_jwt(
        {
            "sub": "google-oauth2|1234567890",
            "https://api.openai.com/auth": {"chatgpt_account_id": "acct-123"},
        }
    )

    state = codex_quota.persist_codex_headers(
        {
            "x-codex-primary-used-percent": "85",
            "x-codex-secondary-used-percent": "42",
            "x-codex-primary-reset-at": "1777005338",
            "x-codex-secondary-reset-at": "1777400433",
        },
        access_token=token,
        observed_at=1776988344,
        source="profile:myknot",
    )

    state_path = tmp_path / "global" / "state" / "codex_quota_state.json"
    assert state_path.exists()
    persisted = json.loads(state_path.read_text())
    latest = persisted["accounts"]["acct-123"]["latest"]
    assert latest["five_hour_used_pct"] == 85
    assert latest["week_used_pct"] == 42
    assert state == persisted


def test_due_thresholds_only_emit_newly_crossed_levels():
    account_state = {
        "latest": {
            "five_hour_used_pct": 91,
            "week_used_pct": 84,
            "five_hour_reset_at": 1777005338,
            "week_reset_at": 1777400433,
        },
        "notified": {
            "5h": [85],
            "week": [],
        },
    }

    due = codex_quota.due_thresholds(account_state)

    assert due == {"5h": [90], "week": []}


def test_update_state_clears_notified_thresholds_after_reset_window_changes():
    old_state = {
        "accounts": {
            "acct-123": {
                "latest": {
                    "account_key": "acct-123",
                    "five_hour_used_pct": 95,
                    "week_used_pct": 70,
                    "five_hour_reset_at": 1777005338,
                    "week_reset_at": 1777400433,
                },
                "notified": {"5h": [85, 90, 95], "week": [85]},
            }
        }
    }
    new_snapshot = {
        "account_key": "acct-123",
        "five_hour_used_pct": 10,
        "week_used_pct": 71,
        "five_hour_reset_at": 1777020000,
        "week_reset_at": 1777400433,
    }

    updated = codex_quota.update_state_with_snapshot(old_state, new_snapshot)

    assert updated["accounts"]["acct-123"]["notified"]["5h"] == []
    assert updated["accounts"]["acct-123"]["notified"]["week"] == [85]


def test_format_notification_uses_jst_and_compact_week_remaining():
    now = datetime(2026, 4, 24, 8, 53, tzinfo=ZoneInfo("Asia/Tokyo"))
    snapshot = {
        "five_hour_used_pct": 90,
        "week_used_pct": 86,
        "five_hour_reset_at": int(datetime(2026, 4, 24, 13, 35, tzinfo=ZoneInfo("Asia/Tokyo")).timestamp()),
        "week_reset_at": int(datetime(2026, 4, 29, 3, 20, tzinfo=ZoneInfo("Asia/Tokyo")).timestamp()),
    }

    message = codex_quota.format_notification(snapshot, now=now)

    assert message == "5h: 90% used / reset 13:35\nweek: 86% used / reset 4d 18:27"


def test_load_monitor_config_defaults_to_hourly_summary_mode(tmp_path, monkeypatch):
    profile_home = tmp_path / "profiles" / "myknot"
    profile_home.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(profile_home))

    config = codex_quota.load_monitor_config(tmp_path)

    assert config["mode"] == "always"
    assert config["thresholds"] == [85, 90, 95]


def test_run_monitor_sends_message_every_run_in_always_mode(tmp_path, monkeypatch):
    state_path = tmp_path / "global" / "state" / "codex_quota_state.json"
    codex_quota.save_state({"version": 1, "accounts": {}}, state_path)
    config_path = tmp_path / "global" / "config" / "codex_quota_monitor.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "mode": "always",
                "probe_model": "gpt-5.4-mini",
                "delivery": {"discord_channel_id": "123"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        codex_quota,
        "iter_codex_auth_entries",
        lambda root=None: [{"account_key": "acct-123", "access_token": "tok", "auth_path": "/tmp/auth.json", "last_refresh_ts": 1.0}],
    )
    monkeypatch.setattr(codex_quota, "pick_probe_entries", lambda entries: entries)
    monkeypatch.setattr(
        codex_quota,
        "live_probe_codex_quota",
        lambda access_token, source=None, model="gpt-5.4-mini", timeout=60: {
            "account_key": "acct-123",
            "five_hour_used_pct": 11,
            "week_used_pct": 78,
            "five_hour_reset_at": 1777024911,
            "week_reset_at": 1777400433,
            "observed_at": 1777021230,
            "source": source,
        },
    )

    sent = []
    monkeypatch.setattr(codex_quota, "send_discord_message", lambda message, channel_id, bot_token, timeout=30: sent.append(message))
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-token")

    result = codex_quota.run_monitor(root=tmp_path, now=datetime(2026, 4, 24, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo")))

    assert result["silent"] is False
    assert sent == ["5h: 11% used / reset 19:01\nweek: 78% used / reset 4d 18:20"]


def test_process_codex_headers_sends_threshold_notification_once(tmp_path, monkeypatch):
    profile_home = tmp_path / "profiles" / "myknot"
    profile_home.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(profile_home))

    config_path = tmp_path / "global" / "config" / "codex_quota_monitor.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "mode": "always",
                "delivery": {"discord_channel_id": "summary-channel"},
                "message_event": {
                    "enabled": True,
                    "thresholds": [85, 90, 95],
                    "discord_channel_id": "threshold-channel",
                },
            }
        ),
        encoding="utf-8",
    )

    token = _fake_jwt(
        {
            "sub": "google-oauth2|1234567890",
            "https://api.openai.com/auth": {"chatgpt_account_id": "acct-123"},
        }
    )
    headers = {
        "x-codex-primary-used-percent": "90",
        "x-codex-secondary-used-percent": "60",
        "x-codex-primary-reset-at": "1777005338",
        "x-codex-secondary-reset-at": "1777400433",
    }

    sent = []
    monkeypatch.setattr(
        codex_quota,
        "send_discord_message",
        lambda message, channel_id, bot_token, timeout=30: sent.append((message, channel_id)),
    )
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-token")

    first = codex_quota.process_codex_headers(
        headers,
        access_token=token,
        observed_at=1776988344,
        source="profile:myknot",
        now=datetime(2026, 4, 24, 8, 48, tzinfo=ZoneInfo("Asia/Tokyo")),
    )
    second = codex_quota.process_codex_headers(
        headers,
        access_token=token,
        observed_at=1776988400,
        source="profile:myknot",
        now=datetime(2026, 4, 24, 8, 49, tzinfo=ZoneInfo("Asia/Tokyo")),
    )

    assert first["snapshot"]["five_hour_used_pct"] == 90
    assert first["threshold_notification_sent"] is True
    assert second["threshold_notification_sent"] is False
    assert sent == [(
        "5h: 90% used / reset 13:35\nweek: 60% used / reset 4d 18:32",
        "threshold-channel",
    )]
