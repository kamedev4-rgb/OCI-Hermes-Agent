from __future__ import annotations

import json
import os
import shlex
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import yaml

from hermes_constants import get_hermes_home

TOOL_NAME = "mycare_approval_token"
TOOLSET = "hermes-discord"
DEFAULT_ACTION = "mycare_service_repair"
DEFAULT_EXPIRES_HOURS = 24
DEFAULT_ALLOW_ADMIN_BYPASS = True
_DEFAULT_COMPOSE_PATH = Path("/home/ubuntu/myknot/docker-compose.yml")


def _get_session_user_id() -> str:
    from gateway.session_context import get_session_env

    return (get_session_env("HERMES_SESSION_USER_ID", "") or "").strip()


def _get_session_user_name() -> str:
    from gateway.session_context import get_session_env

    return (get_session_env("HERMES_SESSION_USER_NAME", "") or "").strip()


def _load_profile_plugin_config() -> dict[str, Any]:
    cfg_path = get_hermes_home() / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        data = yaml.safe_load(cfg_path.read_text()) or {}
    except Exception:
        return {}
    section = data.get("mycare_approval")
    return section if isinstance(section, dict) else {}


def _normalize_user_ids(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        items = [str(part).strip() for part in raw]
    else:
        return set()
    return {item for item in items if item}


def _get_admin_user_ids() -> set[str]:
    cfg = _load_profile_plugin_config()
    ids = _normalize_user_ids(cfg.get("admin_user_ids"))
    env_ids = _normalize_user_ids(os.getenv("MYCARE_APPROVAL_ADMIN_USER_IDS", ""))
    return ids | env_ids


def _allow_admin_bypass() -> bool:
    cfg = _load_profile_plugin_config()
    raw = cfg.get("allow_admin_bypass", DEFAULT_ALLOW_ADMIN_BYPASS)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(raw)


@dataclass
class DbConfig:
    host: str = "127.0.0.1"
    port: int = 5432
    dbname: str = "myknot"
    user: str = "myknot"
    password: str = ""


def _load_db_config(compose_path: Path = _DEFAULT_COMPOSE_PATH) -> DbConfig:
    cfg = DbConfig()
    if compose_path.exists():
        try:
            data = yaml.safe_load(compose_path.read_text()) or {}
            postgres = ((data.get("services") or {}).get("postgres") or {})
            env = postgres.get("environment") or {}
            cfg.dbname = str(env.get("POSTGRES_DB") or cfg.dbname)
            cfg.user = str(env.get("POSTGRES_USER") or cfg.user)
            cfg.password = str(env.get("POSTGRES_PASSWORD") or cfg.password)
            ports = postgres.get("ports") or []
            if ports:
                raw = str(ports[0]).strip().strip('"').strip("'")
                host_port = raw.split(":")[-2] if raw.count(":") >= 2 else raw.split(":")[0]
                cfg.port = int(host_port)
        except Exception:
            pass
    return cfg


class PostgresApprovalTokenRepo:
    def __init__(self, db_config: Optional[DbConfig] = None):
        self.db_config = db_config or _load_db_config()

    def _connect(self):
        return psycopg.connect(
            host=self.db_config.host,
            port=self.db_config.port,
            dbname=self.db_config.dbname,
            user=self.db_config.user,
            password=self.db_config.password,
            row_factory=dict_row,
        )

    def ensure_schema(self):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE approval_tokens "
                "ADD COLUMN IF NOT EXISTS requested_by_user_id text"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS approval_tokens_requested_by_user_id_idx "
                "ON approval_tokens (requested_by_user_id)"
            )
            cur.execute(
                "UPDATE approval_tokens "
                "SET requested_by_user_id = COALESCE(requested_by_user_id, params->>'requested_by_user_id') "
                "WHERE requested_by_user_id IS NULL "
                "AND params IS NOT NULL "
                "AND params ? 'requested_by_user_id'"
            )
            conn.commit()

    def issue_token(
        self,
        *,
        requested_by_user_id: str,
        action: str,
        params: dict[str, Any],
        expires_hours: int,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO approval_tokens (
                    action,
                    params,
                    status,
                    expires_at,
                    requested_by_user_id
                )
                VALUES (
                    %s,
                    %s,
                    'approved',
                    NOW() + make_interval(hours => %s),
                    %s
                )
                RETURNING
                    token::text AS token,
                    requested_by_user_id,
                    action,
                    COALESCE(params, '{}'::jsonb) AS params,
                    status,
                    expires_at
                """,
                (action, Jsonb(params), int(expires_hours), requested_by_user_id),
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row or {})

    def get_token(self, token: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    token::text AS token,
                    requested_by_user_id,
                    action,
                    COALESCE(params, '{}'::jsonb) AS params,
                    status,
                    expires_at
                FROM approval_tokens
                WHERE token = %s::uuid
                """,
                (token,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


class ApprovalTokenService:
    def __init__(
        self,
        repo: Optional[Any] = None,
        session_user_id_getter: Optional[Callable[[], str]] = None,
        session_user_name_getter: Optional[Callable[[], str]] = None,
        admin_user_ids_getter: Optional[Callable[[], set[str]]] = None,
        allow_admin_bypass_getter: Optional[Callable[[], bool]] = None,
    ):
        self.repo = repo or PostgresApprovalTokenRepo()
        self.session_user_id_getter = session_user_id_getter or _get_session_user_id
        self.session_user_name_getter = session_user_name_getter or _get_session_user_name
        self.admin_user_ids_getter = admin_user_ids_getter or _get_admin_user_ids
        self.allow_admin_bypass_getter = allow_admin_bypass_getter or _allow_admin_bypass

    def _current_user_id(self) -> str:
        return (self.session_user_id_getter() or "").strip()

    def _current_user_name(self) -> str:
        return (self.session_user_name_getter() or "").strip()

    def admin_user_ids(self) -> set[str]:
        try:
            return {uid for uid in self.admin_user_ids_getter() if uid}
        except Exception:
            return set()

    def is_admin_user(self, user_id: Optional[str] = None) -> bool:
        resolved = (user_id or self._current_user_id()).strip()
        return bool(resolved and resolved in self.admin_user_ids())

    def issue_token(
        self,
        *,
        action: str = DEFAULT_ACTION,
        params: Optional[dict[str, Any]] = None,
        expires_hours: int = DEFAULT_EXPIRES_HOURS,
    ) -> dict[str, Any]:
        user_id = self._current_user_id()
        if not user_id:
            return {
                "ok": False,
                "reason": "missing_user_id",
                "message": "Current session has no user ID, so the approval token cannot be bound.",
            }
        if not self.is_admin_user(user_id):
            return {
                "ok": False,
                "reason": "admin_required",
                "message": "Only configured system administrators can issue MyCARE approval tokens.",
            }

        merged_params = dict(params or {})
        requester_name = self._current_user_name()
        if requester_name:
            merged_params.setdefault("requested_by_user_name", requester_name)
        self.repo.ensure_schema()
        row = self.repo.issue_token(
            requested_by_user_id=user_id,
            action=action,
            params=merged_params,
            expires_hours=max(1, int(expires_hours)),
        )
        return {
            "ok": True,
            "token": row.get("token"),
            "action": row.get("action", action),
            "requested_by_user_id": row.get("requested_by_user_id", user_id),
            "params": row.get("params", merged_params),
            "status": row.get("status", "approved"),
            "expires_at": _isoformat(row.get("expires_at")),
            "message": "Approval token issued and bound to the current user ID.",
        }

    def validate_token(self, token: str) -> dict[str, Any]:
        raw_token = (token or "").strip()
        user_id = self._current_user_id()
        if not user_id:
            return {
                "ok": False,
                "reason": "missing_user_id",
                "message": "Current session has no user ID, so the approval token cannot be checked.",
            }

        if self.is_admin_user(user_id) and self.allow_admin_bypass_getter():
            if not raw_token:
                return {
                    "ok": True,
                    "valid": True,
                    "reason": "admin_bypass",
                    "requested_by_user_id": user_id,
                    "message": "Configured administrator bypassed token validation.",
                }

        if not raw_token:
            return {
                "ok": False,
                "reason": "missing_token",
                "message": "A token is required.",
            }

        try:
            uuid.UUID(raw_token)
        except ValueError:
            return {
                "ok": False,
                "reason": "invalid_token_format",
                "message": "Approval tokens must be UUID strings.",
            }

        self.repo.ensure_schema()
        row = self.repo.get_token(raw_token)
        if not row:
            return {
                "ok": False,
                "reason": "not_found",
                "message": "Approval token not found.",
            }

        owner_user_id = (row.get("requested_by_user_id") or "").strip()
        if not owner_user_id:
            return {
                "ok": False,
                "reason": "unbound_token",
                "token": raw_token,
                "message": "The token exists but is not bound to a user ID.",
            }
        if owner_user_id != user_id:
            return {
                "ok": False,
                "reason": "wrong_user",
                "token": raw_token,
                "requested_by_user_id": owner_user_id,
                "message": "This token belongs to a different user ID.",
            }

        status = (row.get("status") or "").strip().lower()
        if status != "approved":
            return {
                "ok": False,
                "reason": "invalid_status",
                "token": raw_token,
                "status": row.get("status"),
                "requested_by_user_id": owner_user_id,
                "message": "The token exists but is not approved.",
            }

        expires_at = _coerce_datetime(row.get("expires_at"))
        if expires_at and expires_at <= datetime.now(timezone.utc):
            return {
                "ok": False,
                "reason": "expired",
                "token": raw_token,
                "requested_by_user_id": owner_user_id,
                "expires_at": _isoformat(expires_at),
                "message": "The token has expired.",
            }

        return {
            "ok": True,
            "valid": True,
            "token": raw_token,
            "action": row.get("action"),
            "params": row.get("params") or {},
            "status": row.get("status"),
            "requested_by_user_id": owner_user_id,
            "expires_at": _isoformat(expires_at),
            "message": "The token is valid for the current user ID.",
        }


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _isoformat(value: Any) -> Optional[str]:
    dt = _coerce_datetime(value)
    return dt.isoformat() if dt else None


def _tool_handler(args: dict[str, Any], **_kwargs) -> str:
    service = ApprovalTokenService()
    action = (args.get("action") or "").strip().lower()
    if action == "issue":
        result = service.issue_token(
            action=(args.get("approval_action") or DEFAULT_ACTION).strip() or DEFAULT_ACTION,
            params=args.get("params") if isinstance(args.get("params"), dict) else {},
            expires_hours=int(args.get("expires_hours") or DEFAULT_EXPIRES_HOURS),
        )
    elif action == "validate":
        result = service.validate_token(str(args.get("token") or ""))
    else:
        result = {
            "ok": False,
            "reason": "unsupported_action",
            "message": "Supported actions are 'issue' and 'validate'.",
        }
    return json.dumps(result, ensure_ascii=False)


def _issue_command(raw_args: str) -> str:
    try:
        parts = shlex.split(raw_args or "")
    except ValueError as exc:
        return f"発行失敗: 引数の解釈に失敗しました ({exc})"
    action = parts[0] if parts else DEFAULT_ACTION
    label = " ".join(parts[1:]).strip()
    params = {"requested_label": label} if label else {}
    result = ApprovalTokenService().issue_token(action=action, params=params)
    if not result.get("ok"):
        return f"発行失敗: {result.get('message')}"
    token = result.get("token") or ""
    return (
        "承認トークンを発行しました。\n"
        f"- token: `{token}`\n"
        f"- action: `{result.get('action')}`\n"
        f"- bound user_id: `{result.get('requested_by_user_id')}`\n"
        f"- expires_at: `{result.get('expires_at')}`"
    )


def _validate_command(raw_args: str) -> str:
    result = ApprovalTokenService().validate_token(raw_args.strip())
    if result.get("ok"):
        if result.get("reason") == "admin_bypass":
            return (
                "管理者bypassが有効です。\n"
                f"- user_id: `{result.get('requested_by_user_id')}`\n"
                "- token: 不要"
            )
        return (
            "承認トークンは有効です。\n"
            f"- token: `{result.get('token')}`\n"
            f"- action: `{result.get('action')}`\n"
            f"- user_id: `{result.get('requested_by_user_id')}`\n"
            f"- expires_at: `{result.get('expires_at')}`"
        )
    return (
        "承認トークンは無効です。\n"
        f"- reason: `{result.get('reason')}`\n"
        f"- message: {result.get('message')}"
    )


def register(ctx):
    ctx.register_tool(
        name=TOOL_NAME,
        toolset=TOOLSET,
        schema={
            "name": TOOL_NAME,
            "description": "Issue or validate MyCARE approval tokens. Only configured admins can issue, and admins may bypass validation without a token.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["issue", "validate"],
                        "description": "Whether to issue a token or validate an existing one.",
                    },
                    "approval_action": {
                        "type": "string",
                        "description": "Business action recorded on issue, such as mycare_service_repair.",
                    },
                    "params": {
                        "type": "object",
                        "description": "Optional JSON parameters stored with the token on issue.",
                        "additionalProperties": True,
                    },
                    "expires_hours": {
                        "type": "integer",
                        "description": "Hours until expiration when issuing a token.",
                        "minimum": 1,
                    },
                    "token": {
                        "type": "string",
                        "description": "UUID token to validate. Leave empty for admin bypass checks.",
                    },
                },
                "required": ["action"],
            },
        },
        handler=_tool_handler,
        description="MyCARE approval tokens with admin-only issuing and admin bypass.",
    )
    ctx.register_command(
        "mycare-issue-token",
        _issue_command,
        description="Issue a MyCARE approval token. Admin users only.",
    )
    ctx.register_command(
        "mycare-validate-token",
        _validate_command,
        description="Validate a MyCARE token, or confirm admin bypass when no token is given.",
    )
