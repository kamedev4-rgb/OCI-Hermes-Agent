"""Tests for automatic session restoration in Discord threads after auto-reset."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.session import SessionEntry, SessionSource, SessionStore
from gateway.run import GatewayRunner


def _discord_thread_source(chat_id="chan-1", thread_id="thread-1", user_id="user-1"):
    return SessionSource(
        platform=Platform.DISCORD,
        chat_id=chat_id,
        chat_type="thread",
        thread_id=thread_id,
        user_id=user_id,
        user_name="tester",
    )


def _make_store(tmp_path, *, idle_minutes=1):
    config = GatewayConfig()
    config.default_reset_policy.idle_minutes = idle_minutes
    config.default_reset_policy.mode = "idle"
    config.auto_resume_thread_sessions = True
    config.auto_resume_thread_platforms = ["discord"]
    config.auto_resume_thread_max_age_hours = 168
    config.auto_resume_thread_min_messages = 2
    return SessionStore(sessions_dir=tmp_path / "sessions", config=config)


class TestThreadAutoResumeConfig:
    def test_defaults_disabled(self):
        config = GatewayConfig()
        assert config.auto_resume_thread_sessions is False
        assert config.auto_resume_thread_platforms == ["discord"]
        assert config.auto_resume_thread_max_age_hours == 168
        assert config.auto_resume_thread_min_messages == 4


class TestThreadAutoResumeSessionStore:
    def test_auto_reset_tracks_resume_candidate_for_discord_thread(self, tmp_path):
        store = _make_store(tmp_path)
        source = _discord_thread_source()

        entry1 = store.get_or_create_session(source)
        old_session_id = entry1.session_id
        store.append_to_transcript(old_session_id, {"role": "user", "content": "hello"})
        store.append_to_transcript(old_session_id, {"role": "assistant", "content": "world"})
        entry1.total_tokens = 100
        entry1.updated_at = datetime.now() - timedelta(minutes=5)
        store._save()

        entry2 = store.get_or_create_session(source)

        assert entry2.was_auto_reset is True
        assert entry2.auto_reset_reason == "idle"
        assert entry2.resume_candidate_session_id == old_session_id

    def test_auto_resume_target_uses_candidate_when_history_is_long_enough(self, tmp_path):
        store = _make_store(tmp_path)
        source = _discord_thread_source()

        entry1 = store.get_or_create_session(source)
        old_session_id = entry1.session_id
        store.append_to_transcript(old_session_id, {"role": "user", "content": "one"})
        store.append_to_transcript(old_session_id, {"role": "assistant", "content": "two"})
        entry1.total_tokens = 100
        entry1.updated_at = datetime.now() - timedelta(minutes=5)
        store._save()

        entry2 = store.get_or_create_session(source)

        assert store.get_auto_resume_target(entry2, source) == old_session_id

    def test_auto_resume_target_skips_suspended_sessions(self, tmp_path):
        store = _make_store(tmp_path)
        source = _discord_thread_source()

        entry1 = store.get_or_create_session(source)
        entry1.suspended = True
        entry1.updated_at = datetime.now() - timedelta(minutes=5)
        store._save()

        entry2 = store.get_or_create_session(source)

        assert entry2.auto_reset_reason == "suspended"
        assert store.get_auto_resume_target(entry2, source) is None

    def test_session_entry_roundtrip_preserves_resume_candidate(self):
        entry = SessionEntry(
            session_key="agent:main:discord:thread:chan-1:thread-1",
            session_id="new-session",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            platform=Platform.DISCORD,
            chat_type="thread",
            resume_candidate_session_id="old-session",
        )

        restored = SessionEntry.from_dict(entry.to_dict())

        assert restored.resume_candidate_session_id == "old-session"


class TestThreadAutoResumeRunner:
    def test_runner_switches_to_previous_session(self, tmp_path):
        store = _make_store(tmp_path)
        source = _discord_thread_source()

        old_entry = store.get_or_create_session(source)
        store.append_to_transcript(old_entry.session_id, {"role": "user", "content": "one"})
        store.append_to_transcript(old_entry.session_id, {"role": "assistant", "content": "two"})
        old_entry.total_tokens = 100
        old_entry.updated_at = datetime.now() - timedelta(minutes=5)
        store._save()
        new_entry = store.get_or_create_session(source)

        runner = GatewayRunner.__new__(GatewayRunner)
        runner.session_store = store
        runner._release_running_agent_state = MagicMock()

        resumed = runner._maybe_auto_resume_thread_session(source, new_entry)

        assert resumed.session_id == old_entry.session_id
        runner._release_running_agent_state.assert_called_once_with(new_entry.session_key)
