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
