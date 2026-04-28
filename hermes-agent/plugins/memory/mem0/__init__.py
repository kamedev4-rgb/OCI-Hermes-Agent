"""Mem0 memory plugin — MemoryProvider interface (OSS edition).

Uses the open-source ``mem0`` library (Memory.from_config) instead of the
cloud MemoryClient, so no Mem0 Platform API key is required.

LLM backend is selected via mem0.json ``llm_provider`` key:
  "openai-codex"  — ChatGPT Plus OAuth (auto-refreshed via Hermes auth)
  "qwen-oauth"    — Qwen OAuth (auto-refreshed via Hermes auth)
  "zai"           — Z.AI / GLM  (GLM_API_KEY / ZAI_API_KEY env var)
  "openai"        — Standard OpenAI API key / NVIDIA NIM (OPENAI_API_KEY env var)

Default LLM model per provider:
  openai-codex → gpt-4.1
  qwen-oauth   → qwen-plus
  zai          → glm-4-flash
  openai       → gpt-4o-mini

For NVIDIA NIM, set llm_provider=openai, OPENAI_API_KEY=nvapi-xxx,
and llm_base_url=https://integrate.api.nvidia.com/v1 in mem0.json.

Vector store: always PostgreSQL + pgvector (configured in mem0.json / env).
Embedder: always HuggingFace intfloat/multilingual-e5-base (local, no key needed).

Required mem0.json keys:
  pg_host, pg_port, pg_user, pg_password, pg_dbname  — PostgreSQL connection
  llm_provider  — one of the above (default: openai-codex)

Optional mem0.json keys:
  llm_model      — override the default model for the selected provider
  llm_base_url   — override the inference endpoint (NVIDIA NIM etc.)
  user_id        — default user identifier (default: hermes-user)
  agent_id       — default agent identifier (default: hermes)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

logger = logging.getLogger(__name__)

_BREAKER_THRESHOLD = 5
_BREAKER_COOLDOWN_SECS = 120

_DEFAULT_MODELS = {
    "openai-codex": "gpt-4.1",
    "qwen-oauth": "qwen-plus",
    "zai": "glm-4-flash",
    "openai": "gpt-4o-mini",
}


def _current_profile_name() -> str:
    """Return the active named profile, or empty string for the default root."""
    from hermes_constants import get_hermes_home

    home = get_hermes_home()
    return home.name if home.parent.name == "profiles" else ""


def _default_pg_dbname() -> str:
    """Default per-profile PostgreSQL DB name for Mem0."""
    profile = _current_profile_name()
    if profile:
        return profile.replace("-", "_")
    return os.environ.get("POSTGRES_DB", "myknot")


def _default_agent_id() -> str:
    """Default per-profile agent identifier for Mem0 attribution."""
    profile = _current_profile_name()
    return profile or "hermes"


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load PostgreSQL + LLM provider config from env and mem0.json."""
    from hermes_constants import get_hermes_home

    config = {
        "pg_host": os.environ.get("MEM0_PG_HOST", "localhost"),
        "pg_port": int(os.environ.get("MEM0_PG_PORT", "5432")),
        "pg_user": os.environ.get("MEM0_PG_USER", os.environ.get("POSTGRES_USER", "myknot")),
        "pg_password": os.environ.get("MEM0_PG_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "")),
        "pg_dbname": os.environ.get("MEM0_PG_DBNAME", _default_pg_dbname()),
        "llm_provider": os.environ.get("MEM0_LLM_PROVIDER", "openai-codex"),
        "llm_model": os.environ.get("MEM0_LLM_MODEL", ""),
        "llm_base_url": os.environ.get("MEM0_LLM_BASE_URL", ""),
        "user_id": os.environ.get("MEM0_USER_ID", "hermes-user"),
        "agent_id": os.environ.get("MEM0_AGENT_ID", _default_agent_id()),
    }

    config_path = get_hermes_home() / "mem0.json"
    if config_path.exists():
        try:
            file_cfg = json.loads(config_path.read_text(encoding="utf-8"))
            config.update({k: v for k, v in file_cfg.items()
                           if v is not None and v != ""})
        except Exception:
            pass

    return config


def _resolve_llm_config(provider: str, model_override: str, base_url_override: str) -> dict:
    """Build a Mem0-compatible LLM config dict for the given provider.

    For OAuth providers, tokens are fetched fresh each time so that expiry
    is handled transparently without caching a stale token in the plugin.
    """
    model = model_override or _DEFAULT_MODELS.get(provider, "gpt-4o-mini")

    if provider == "openai-codex":
        try:
            from hermes_cli.auth import resolve_codex_runtime_credentials
            creds = resolve_codex_runtime_credentials()
            return {
                "provider": "openai",
                "config": {
                    "model": model,
                    "api_key": creds["api_key"],
                    "openai_base_url": base_url_override or creds["base_url"],
                },
            }
        except Exception as e:
            raise RuntimeError(f"Codex OAuth token unavailable: {e}. Run `hermes auth` to authenticate.") from e

    if provider == "qwen-oauth":
        try:
            from hermes_cli.auth import resolve_qwen_runtime_credentials
            creds = resolve_qwen_runtime_credentials()
            return {
                "provider": "openai",
                "config": {
                    "model": model,
                    "api_key": creds["api_key"],
                    "openai_base_url": base_url_override or creds["base_url"],
                },
            }
        except Exception as e:
            raise RuntimeError(f"Qwen OAuth token unavailable: {e}. Run `hermes auth` to authenticate.") from e

    if provider == "zai":
        api_key = (
            os.environ.get("GLM_API_KEY")
            or os.environ.get("ZAI_API_KEY")
            or os.environ.get("Z_AI_API_KEY")
            or ""
        ).strip()
        if not api_key:
            raise RuntimeError(
                "Z.AI / GLM API key not found. Set GLM_API_KEY or ZAI_API_KEY in .env."
            )
        return {
            "provider": "openai",
            "config": {
                "model": model,
                "api_key": api_key,
                "openai_base_url": base_url_override or "https://api.z.ai/api/paas/v4",
            },
        }

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set.")
        cfg: Dict[str, Any] = {"model": model, "api_key": api_key}
        if base_url_override:
            cfg["openai_base_url"] = base_url_override
        return {"provider": "openai", "config": cfg}

    raise RuntimeError(
        f"Unknown llm_provider: '{provider}'. "
        "Supported: openai-codex, qwen-oauth, zai, openai"
    )


def _build_mem0_config(cfg: dict) -> dict:
    """Build the full Mem0 config dict (embedder + vector_store + llm)."""
    llm_cfg = _resolve_llm_config(
        cfg["llm_provider"],
        cfg.get("llm_model", ""),
        cfg.get("llm_base_url", ""),
    )
    return {
        "llm": llm_cfg,
        "embedder": {
            "provider": "huggingface",
            "config": {
                "model": "intfloat/multilingual-e5-base",
                "embedding_dims": 768,
            },
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": cfg["pg_host"],
                "port": cfg["pg_port"],
                "user": cfg["pg_user"],
                "password": cfg["pg_password"],
                "dbname": cfg["pg_dbname"],
                "collection_name": "memories",
                "embedding_model_dims": 768,
            },
        },
    }


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

PROFILE_SCHEMA = {
    "name": "mem0_profile",
    "description": (
        "Retrieve all stored memories about the user — preferences, facts, "
        "project context. Fast, no reranking. Use at conversation start."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SEARCH_SCHEMA = {
    "name": "mem0_search",
    "description": (
        "Search memories by meaning. Returns relevant facts ranked by similarity."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "top_k": {"type": "integer", "description": "Max results (default: 10, max: 50)."},
        },
        "required": ["query"],
    },
}

CONCLUDE_SCHEMA = {
    "name": "mem0_conclude",
    "description": (
        "Store a durable fact about the user. Use for explicit preferences, "
        "corrections, or decisions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "conclusion": {"type": "string", "description": "The fact to store."},
        },
        "required": ["conclusion"],
    },
}


# ---------------------------------------------------------------------------
# MemoryProvider implementation
# ---------------------------------------------------------------------------

class Mem0MemoryProvider(MemoryProvider):
    """Mem0 OSS memory with local PostgreSQL + OAuth/APIkey LLM backends."""

    def __init__(self):
        self._config: Optional[dict] = None
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread: Optional[threading.Thread] = None
        self._sync_thread: Optional[threading.Thread] = None
        self._consecutive_failures = 0
        self._breaker_open_until = 0.0

    @property
    def name(self) -> str:
        return "mem0"

    def is_available(self) -> bool:
        """Available when PostgreSQL config is present (no cloud API key needed)."""
        cfg = _load_config()
        return bool(cfg.get("pg_password") or cfg.get("pg_host") != "localhost")

    def get_config_schema(self):
        return [
            {"key": "pg_host", "description": "PostgreSQL host", "default": "localhost"},
            {"key": "pg_port", "description": "PostgreSQL port", "default": "5432"},
            {"key": "pg_user", "description": "PostgreSQL user", "default": "myknot"},
            {"key": "pg_password", "description": "PostgreSQL password", "secret": True, "required": True, "env_var": "MEM0_PG_PASSWORD"},
            {"key": "pg_dbname", "description": "PostgreSQL database name", "default": _default_pg_dbname()},
            {"key": "llm_provider", "description": "LLM backend for memory extraction", "default": "openai-codex", "choices": ["openai-codex", "qwen-oauth", "zai", "openai"]},
            {"key": "llm_model", "description": "Override default model for the selected provider (optional)"},
        ]

    def save_config(self, values, hermes_home):
        from pathlib import Path
        config_path = Path(hermes_home) / "mem0.json"
        existing = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
            except Exception:
                pass
        existing.update(values)
        existing.setdefault("pg_dbname", _default_pg_dbname())
        existing.setdefault("agent_id", _default_agent_id())
        config_path.write_text(json.dumps(existing, indent=2))

    def _is_breaker_open(self) -> bool:
        if self._consecutive_failures < _BREAKER_THRESHOLD:
            return False
        if time.monotonic() >= self._breaker_open_until:
            self._consecutive_failures = 0
            return False
        return True

    def _record_success(self):
        self._consecutive_failures = 0

    def _record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= _BREAKER_THRESHOLD:
            self._breaker_open_until = time.monotonic() + _BREAKER_COOLDOWN_SECS
            logger.warning(
                "Mem0 circuit breaker tripped after %d consecutive failures. "
                "Pausing for %ds.",
                self._consecutive_failures, _BREAKER_COOLDOWN_SECS,
            )

    def _get_client(self):
        """Create a fresh Memory instance with up-to-date OAuth tokens.

        Extracted as its own method so tests can monkeypatch it with a fake client.
        """
        try:
            from mem0 import Memory
        except ImportError:
            raise RuntimeError("mem0 package not installed. Run: pip install mem0ai")
        return Memory.from_config(_build_mem0_config(self._config))

    # Keep _new_mem as an alias so existing call sites continue to work.
    def _new_mem(self):
        return self._get_client()

    def _read_filters(self) -> dict:
        """Filters for read operations (search / get_all).

        Intentionally omits agent_id so memories are recalled across agents
        (cross-session recall design).
        """
        return {"user_id": self._user_id}

    def _write_filters(self) -> dict:
        """Filters for write operations (add).

        Includes agent_id for attribution so each agent's contributions can be
        distinguished when inspecting raw DB rows.
        """
        return {"user_id": self._user_id, "agent_id": self._agent_id}

    def initialize(self, session_id: str, **kwargs) -> None:
        self._config = _load_config()
        self._user_id = kwargs.get("user_id") or self._config.get("user_id", "hermes-user")
        self._agent_id = self._config.get("agent_id", "hermes")

    def system_prompt_block(self) -> str:
        provider = self._config.get("llm_provider", "openai-codex") if self._config else "openai-codex"
        return (
            "# Mem0 Memory\n"
            f"Active. User: {self._user_id}. LLM: {provider}.\n"
            "Use mem0_search to find memories, mem0_conclude to store facts, "
            "mem0_profile for a full overview."
        )

    @staticmethod
    def _unwrap_results(response: Any) -> list:
        if isinstance(response, dict):
            return response.get("results", [])
        if isinstance(response, list):
            return response
        return []

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        if not result:
            return ""
        return f"## Mem0 Memory\n{result}"

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        if self._is_breaker_open():
            return

        def _run():
            try:
                mem = self._get_client()
                results = self._unwrap_results(
                    mem.search(query=query, filters=self._read_filters(), top_k=5)
                )
                if results:
                    lines = [r.get("memory", "") for r in results if r.get("memory")]
                    with self._prefetch_lock:
                        self._prefetch_result = "\n".join(f"- {l}" for l in lines)
                self._record_success()
            except Exception as e:
                self._record_failure()
                logger.debug("Mem0 prefetch failed: %s", e)

        self._prefetch_thread = threading.Thread(target=_run, daemon=True, name="mem0-prefetch")
        self._prefetch_thread.start()

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if self._is_breaker_open():
            return

        def _sync():
            try:
                mem = self._get_client()
                messages = [
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": assistant_content},
                ]
                wf = self._write_filters()
                mem.add(messages, user_id=wf["user_id"], agent_id=wf["agent_id"])
                self._record_success()
            except Exception as e:
                self._record_failure()
                logger.warning("Mem0 sync failed: %s", e)

        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5.0)

        self._sync_thread = threading.Thread(target=_sync, daemon=True, name="mem0-sync")
        self._sync_thread.start()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [PROFILE_SCHEMA, SEARCH_SCHEMA, CONCLUDE_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> str:
        if self._is_breaker_open():
            return json.dumps({
                "error": "Mem0 temporarily unavailable (multiple consecutive failures). Will retry automatically."
            })

        try:
            mem = self._get_client()
        except Exception as e:
            return tool_error(str(e))

        if tool_name == "mem0_profile":
            try:
                memories = self._unwrap_results(
                    mem.get_all(filters=self._read_filters())
                )
                self._record_success()
                if not memories:
                    return json.dumps({"result": "No memories stored yet."})
                lines = [m.get("memory", "") for m in memories if m.get("memory")]
                return json.dumps({"result": "\n".join(lines), "count": len(lines)})
            except Exception as e:
                self._record_failure()
                return tool_error(f"Failed to fetch profile: {e}")

        elif tool_name == "mem0_search":
            query = args.get("query", "")
            if not query:
                return tool_error("Missing required parameter: query")
            top_k = min(int(args.get("top_k", 10)), 50)
            rerank = args.get("rerank", False)
            try:
                results = self._unwrap_results(
                    mem.search(
                        query=query,
                        filters=self._read_filters(),
                        top_k=top_k,
                        rerank=rerank,
                    )
                )
                self._record_success()
                if not results:
                    return json.dumps({"result": "No relevant memories found."})
                items = [{"memory": r.get("memory", ""), "score": r.get("score", 0)} for r in results]
                return json.dumps({"results": items, "count": len(items)})
            except Exception as e:
                self._record_failure()
                return tool_error(f"Search failed: {e}")

        elif tool_name == "mem0_conclude":
            conclusion = args.get("conclusion", "")
            if not conclusion:
                return tool_error("Missing required parameter: conclusion")
            try:
                wf = self._write_filters()
                mem.add(
                    [{"role": "user", "content": conclusion}],
                    user_id=wf["user_id"],
                    agent_id=wf["agent_id"],
                    infer=False,
                )
                self._record_success()
                return json.dumps({"result": "Fact stored."})
            except Exception as e:
                self._record_failure()
                return tool_error(f"Failed to store: {e}")

        return tool_error(f"Unknown tool: {tool_name}")

    def shutdown(self) -> None:
        for t in (self._prefetch_thread, self._sync_thread):
            if t and t.is_alive():
                t.join(timeout=5.0)


def register(ctx) -> None:
    """Register Mem0 OSS as a memory provider plugin."""
    ctx.register_memory_provider(Mem0MemoryProvider())
