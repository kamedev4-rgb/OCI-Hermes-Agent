from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


PLUGIN_PATH = Path("/home/ubuntu/.hermes/profiles/mycare/plugins/mycare_approval/__init__.py")


def load_plugin_module():
    spec = importlib.util.spec_from_file_location("mycare_approval_plugin", PLUGIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load plugin spec from {PLUGIN_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeRepo:
    def __init__(self, *, token_to_issue: str = "issued-token", token_row: dict | None = None):
        self.token_to_issue = token_to_issue
        self.token_row = token_row
        self.issue_calls = []
        self.ensured = 0
        self.fetch_calls = []

    def ensure_schema(self):
        self.ensured += 1

    def issue_token(self, *, requested_by_user_id: str, action: str, params: dict, expires_hours: int):
        self.issue_calls.append(
            {
                "requested_by_user_id": requested_by_user_id,
                "action": action,
                "params": params,
                "expires_hours": expires_hours,
            }
        )
        return {
            "token": self.token_to_issue,
            "requested_by_user_id": requested_by_user_id,
            "action": action,
            "params": params,
            "status": "approved",
            "expires_in_hours": expires_hours,
        }

    def get_token(self, token: str):
        self.fetch_calls.append(token)
        return self.token_row


def make_service(plugin, repo, *, user_id: str, admin_ids: set[str] | None = None):
    return plugin.ApprovalTokenService(
        repo=repo,
        session_user_id_getter=lambda: user_id,
        admin_user_ids_getter=lambda: set(admin_ids or set()),
    )


def test_issue_binds_current_session_user_id():
    plugin = load_plugin_module()
    repo = FakeRepo(token_to_issue="tok-123")
    service = make_service(plugin, repo, user_id="discord-user-42", admin_ids={"discord-user-42"})

    result = service.issue_token(action="mycare_service_repair", params={"scope": "repair"}, expires_hours=12)

    assert result["ok"] is True
    assert result["token"] == "tok-123"
    assert repo.issue_calls == [
        {
            "requested_by_user_id": "discord-user-42",
            "action": "mycare_service_repair",
            "params": {"scope": "repair"},
            "expires_hours": 12,
        }
    ]
    assert repo.ensured == 1


def test_non_admin_cannot_issue_token():
    plugin = load_plugin_module()
    repo = FakeRepo()
    service = make_service(plugin, repo, user_id="discord-user-42", admin_ids={"discord-admin-1"})

    result = service.issue_token(action="mycare_service_repair")

    assert result["ok"] is False
    assert result["reason"] == "admin_required"
    assert repo.issue_calls == []


def test_admin_without_token_gets_bypass_authorization():
    plugin = load_plugin_module()
    repo = FakeRepo()
    service = make_service(plugin, repo, user_id="discord-admin-1", admin_ids={"discord-admin-1"})

    result = service.validate_token("")

    assert result["ok"] is True
    assert result["valid"] is True
    assert result["reason"] == "admin_bypass"
    assert repo.fetch_calls == []


def test_validate_rejects_token_owned_by_another_user():
    plugin = load_plugin_module()
    repo = FakeRepo(
        token_row={
            "token": "123e4567-e89b-12d3-a456-426614174001",
            "requested_by_user_id": "discord-user-99",
            "action": "mycare_service_repair",
            "params": {"scope": "repair"},
            "status": "approved",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
    )
    service = make_service(plugin, repo, user_id="discord-user-42")

    result = service.validate_token("123e4567-e89b-12d3-a456-426614174001")

    assert result["ok"] is False
    assert result["reason"] == "wrong_user"
    assert result["requested_by_user_id"] == "discord-user-99"
    assert repo.fetch_calls == ["123e4567-e89b-12d3-a456-426614174001"]


def test_validate_accepts_matching_active_token():
    plugin = load_plugin_module()
    repo = FakeRepo(
        token_row={
            "token": "123e4567-e89b-12d3-a456-426614174002",
            "requested_by_user_id": "discord-user-42",
            "action": "mycare_service_repair",
            "params": {"scope": "repair"},
            "status": "approved",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
    )
    service = make_service(plugin, repo, user_id="discord-user-42")

    result = service.validate_token("123e4567-e89b-12d3-a456-426614174002")

    assert result["ok"] is True
    assert result["valid"] is True
    assert result["action"] == "mycare_service_repair"
    assert result["requested_by_user_id"] == "discord-user-42"


def test_issue_requires_current_session_user_id():
    plugin = load_plugin_module()
    repo = FakeRepo()
    service = make_service(plugin, repo, user_id="")

    result = service.issue_token(action="mycare_service_repair")

    assert result["ok"] is False
    assert result["reason"] == "missing_user_id"
    assert repo.issue_calls == []
