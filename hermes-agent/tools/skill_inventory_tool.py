#!/usr/bin/env python3
"""Inventory/search/toggle operations over the skill index DB."""

from __future__ import annotations

import json
from typing import Any

from tools.registry import registry, tool_error
from tools.skill_index_db import SkillIndexDB, get_skill_index_db_path



def _serialize_skill_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_name": row.get("skill_name"),
        "category": row.get("category"),
        "description": row.get("description"),
        "source": row.get("source"),
        "enabled": bool(row.get("enabled", 1)),
        "total_count": int(row.get("total_count") or 0),
        "last_used_at": row.get("last_used_at"),
        "score": row.get("score"),
    }



def _update_disabled_config(skill_name: str, enabled: bool, platform: str | None = None) -> None:
    from hermes_cli.config import load_config
    from hermes_cli.skills_config import get_disabled_skills, save_disabled_skills

    config = load_config()
    disabled = get_disabled_skills(config, platform=platform)
    if enabled:
        disabled.discard(skill_name)
    else:
        disabled.add(skill_name)
    save_disabled_skills(config, disabled, platform=platform)



def skill_inventory(
    action: str,
    query: str | None = None,
    include_disabled: bool = False,
    skill_name: str | None = None,
    enabled: bool | None = None,
    platform: str | None = None,
    limit: int = 20,
) -> str:
    try:
        db = SkillIndexDB(get_skill_index_db_path())
        action = (action or "").strip().lower()
        if action in {"list", "search"}:
            rows = db.search_skills(
                query if action == "search" else None,
                include_disabled=include_disabled,
                limit=limit,
            )
            return json.dumps(
                {
                    "success": True,
                    "skills": [_serialize_skill_row(row) for row in rows],
                    "count": len(rows),
                },
                ensure_ascii=False,
            )

        if action == "toggle":
            if not skill_name:
                return tool_error("skill_name is required for toggle", success=False)
            if enabled is None:
                return tool_error("enabled is required for toggle", success=False)
            _update_disabled_config(skill_name, bool(enabled), platform=platform)
            if platform is None:
                db.set_enabled(skill_name, bool(enabled))
            row = db.get_skill(skill_name)
            return json.dumps(
                {
                    "success": True,
                    "skill_name": skill_name,
                    "enabled": bool(enabled),
                    "platform": platform,
                    "skill": _serialize_skill_row(row) if row else None,
                },
                ensure_ascii=False,
            )

        if action == "stats":
            all_rows = db.search_skills(None, include_disabled=True, limit=max(limit, 10000))
            enabled_count = sum(1 for row in all_rows if row.get("enabled", 1))
            return json.dumps(
                {
                    "success": True,
                    "total": len(all_rows),
                    "enabled": enabled_count,
                    "disabled": len(all_rows) - enabled_count,
                },
                ensure_ascii=False,
            )

        return tool_error(f"Unknown action: {action}", success=False)
    except Exception as e:
        return tool_error(str(e), success=False)


SKILL_INVENTORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "skill_inventory",
        "description": "Search, inspect, and toggle skills using the SQLite-backed skill index. Supports including disabled skills in search results.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "search", "toggle", "stats"],
                    "description": "Operation to perform",
                },
                "query": {
                    "type": "string",
                    "description": "Search query for action='search'",
                },
                "include_disabled": {
                    "type": "boolean",
                    "description": "Include disabled skills in list/search results",
                },
                "skill_name": {
                    "type": "string",
                    "description": "Skill to toggle for action='toggle'",
                },
                "enabled": {
                    "type": "boolean",
                    "description": "Desired enabled state for action='toggle'",
                },
                "platform": {
                    "type": "string",
                    "description": "Optional platform-specific toggle target (e.g. discord)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return",
                },
            },
            "required": ["action"],
        },
    },
}

registry.register(
    name="skill_inventory",
    toolset="skills",
    schema=SKILL_INVENTORY_SCHEMA,
    handler=lambda args, **kw: skill_inventory(
        action=args.get("action", ""),
        query=args.get("query"),
        include_disabled=bool(args.get("include_disabled", False)),
        skill_name=args.get("skill_name"),
        enabled=args.get("enabled"),
        platform=args.get("platform"),
        limit=int(args.get("limit", 20) or 20),
    ),
    emoji="📚",
)
