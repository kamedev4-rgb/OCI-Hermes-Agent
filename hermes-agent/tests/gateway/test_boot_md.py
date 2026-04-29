"""Tests for the built-in boot-md gateway hook."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import hermes_constants
from gateway.builtin_hooks import boot_md


def _reload_boot_md(monkeypatch, tmp_path, profile_name="myknot"):
    """Reload boot_md with a profile-scoped HERMES_HOME under a fake ~/.hermes root."""
    hermes_root = tmp_path / ".hermes"
    profile_home = hermes_root / "profiles" / profile_name
    profile_home.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(profile_home))
    monkeypatch.setattr(hermes_constants.Path, "home", lambda: tmp_path)
    module = importlib.reload(boot_md)
    return module, hermes_root, profile_home


class TestBootMdHook:
    def test_boot_file_uses_root_hermes_dir_when_profile_active(self, monkeypatch, tmp_path):
        module, hermes_root, profile_home = _reload_boot_md(monkeypatch, tmp_path)

        assert profile_home != hermes_root
        assert module.BOOT_FILE == hermes_root / "BOOT.md"

    @pytest.mark.asyncio
    async def test_handle_uses_root_boot_md_when_profile_boot_missing(self, monkeypatch, tmp_path):
        module, hermes_root, profile_home = _reload_boot_md(monkeypatch, tmp_path)
        root_boot = hermes_root / "BOOT.md"
        root_boot.write_text("run self-refactor-post", encoding="utf-8")
        assert not (profile_home / "BOOT.md").exists()

        started = {}

        class FakeThread:
            def __init__(self, *, target, args, name, daemon):
                started["target"] = target
                started["args"] = args
                started["name"] = name
                started["daemon"] = daemon

            def start(self):
                started["started"] = True

        monkeypatch.setattr(module.threading, "Thread", FakeThread)

        await module.handle("gateway:startup", {"platforms": ["discord"]})

        assert started["target"] is module._run_boot_agent
        assert started["args"] == ("run self-refactor-post",)
        assert started["name"] == "boot-md"
        assert started["daemon"] is True
        assert started["started"] is True


class TestRunBootAgent:
    """Unit tests for _run_boot_agent failure handling."""

    def _make_agent(self, monkeypatch, module, result):
        """Patch AIAgent so run_conversation returns *result*."""
        class FakeAgent:
            def __init__(self, **kwargs):
                pass
            def run_conversation(self, prompt):
                return result

        monkeypatch.setattr(module, "AIAgent", FakeAgent, raising=False)
        # Ensure the import inside _run_boot_agent resolves our fake
        import types
        fake_run_agent = types.ModuleType("run_agent")
        fake_run_agent.AIAgent = FakeAgent
        import sys
        monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)

    def test_failed_result_logs_error_not_completed(self, monkeypatch, tmp_path, caplog):
        """When run_conversation returns failed=True the hook must log an error, not 'completed'."""
        import importlib
        import hermes_constants
        from gateway.builtin_hooks import boot_md as module

        module = importlib.reload(module)

        failed_result = {
            "final_response": None,
            "completed": False,
            "failed": True,
            "error": "403 Cloudflare challenge",
        }
        self._make_agent(monkeypatch, module, failed_result)

        import logging
        with caplog.at_level(logging.ERROR, logger="hooks.boot-md"):
            module._run_boot_agent("do something")

        assert any("did not complete" in r.message for r in caplog.records), (
            "Expected 'did not complete' error log, got: " + str([r.message for r in caplog.records])
        )
        assert not any("boot-md completed" in r.message for r in caplog.records)

    def test_not_completed_result_logs_error(self, monkeypatch, tmp_path, caplog):
        """When completed=False (without explicit failed flag) the hook must still log error."""
        import importlib
        from gateway.builtin_hooks import boot_md as module

        module = importlib.reload(module)

        incomplete_result = {
            "final_response": None,
            "completed": False,
            "failed": False,
            "error": "interrupted",
        }
        self._make_agent(monkeypatch, module, incomplete_result)

        import logging
        with caplog.at_level(logging.ERROR, logger="hooks.boot-md"):
            module._run_boot_agent("do something")

        assert any("did not complete" in r.message for r in caplog.records)

    def test_successful_silent_result_logs_nothing_to_report(self, monkeypatch, caplog):
        """When agent succeeds with [SILENT] response, log 'nothing to report'."""
        import importlib
        from gateway.builtin_hooks import boot_md as module

        module = importlib.reload(module)

        success_result = {
            "final_response": "[SILENT]",
            "completed": True,
            "failed": False,
            "error": None,
        }
        self._make_agent(monkeypatch, module, success_result)

        import logging
        with caplog.at_level(logging.INFO, logger="hooks.boot-md"):
            module._run_boot_agent("do something")

        assert any("nothing to report" in r.message for r in caplog.records)

    def test_successful_response_logs_completed(self, monkeypatch, caplog):
        """When agent succeeds with a real response, log 'boot-md completed'."""
        import importlib
        from gateway.builtin_hooks import boot_md as module

        module = importlib.reload(module)

        success_result = {
            "final_response": "All checks passed",
            "completed": True,
            "failed": False,
            "error": None,
        }
        self._make_agent(monkeypatch, module, success_result)

        import logging
        with caplog.at_level(logging.INFO, logger="hooks.boot-md"):
            module._run_boot_agent("do something")

        assert any("boot-md completed" in r.message and "nothing" not in r.message
                   for r in caplog.records)
