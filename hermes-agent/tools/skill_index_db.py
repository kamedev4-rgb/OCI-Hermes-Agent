"""SQLite-backed skill index for search, usage tracking, and prompt shortlist retrieval."""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from hermes_constants import get_hermes_home

_TOKEN_RE = re.compile(r"[a-z0-9_+-]+")
_CJK_CHUNK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fffー]{2,}")
_MAX_TOKENS = 64


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS skills (
    skill_name TEXT PRIMARY KEY,
    category TEXT,
    description TEXT,
    source TEXT NOT NULL,
    skill_dir TEXT,
    skill_path TEXT,
    tags_json TEXT,
    aliases_json TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    pinned INTEGER NOT NULL DEFAULT 0,
    hidden_from_prompt INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_seen_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    used_at REAL NOT NULL,
    session_id TEXT,
    platform TEXT,
    trigger TEXT NOT NULL,
    FOREIGN KEY (skill_name) REFERENCES skills(skill_name)
);

CREATE TABLE IF NOT EXISTS skill_usage_rollups (
    skill_name TEXT PRIMARY KEY,
    total_count INTEGER NOT NULL DEFAULT 0,
    last_used_at REAL,
    used_30d INTEGER NOT NULL DEFAULT 0,
    used_90d INTEGER NOT NULL DEFAULT 0,
    used_discord_90d INTEGER NOT NULL DEFAULT 0,
    used_cli_90d INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (skill_name) REFERENCES skills(skill_name)
);

CREATE INDEX IF NOT EXISTS idx_skill_usage_events_skill_used_at
    ON skill_usage_events(skill_name, used_at DESC);
"""


def get_skill_index_db_path(skills_dir: Path | None = None) -> Path:
    if skills_dir is not None:
        return Path(skills_dir).resolve().parent / "skill_index.db"
    return get_hermes_home() / "skill_index.db"


class SkillIndexDB:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else get_skill_index_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _normalize_skill_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        now = float(metadata.get("now") or time.time())
        return {
            "skill_name": str(metadata.get("skill_name") or metadata.get("name") or "").strip(),
            "category": _normalize_text(metadata.get("category")),
            "description": _normalize_text(metadata.get("description")),
            "source": _normalize_text(metadata.get("source")) or "local",
            "skill_dir": _normalize_text(metadata.get("skill_dir")),
            "skill_path": _normalize_text(metadata.get("skill_path")),
            "tags_json": _json_dumps(metadata.get("tags") or []),
            "aliases_json": _json_dumps(metadata.get("aliases") or []),
            "enabled": int(bool(metadata.get("enabled", True))),
            "pinned": int(bool(metadata.get("pinned", False))),
            "hidden_from_prompt": int(bool(metadata.get("hidden_from_prompt", False))),
            "created_at": now,
            "updated_at": now,
            "last_seen_at": now,
        }

    def upsert_skill(self, metadata: dict[str, Any]) -> None:
        payload = self._normalize_skill_payload(metadata)
        if not payload["skill_name"]:
            raise ValueError("skill_name is required")
        self._conn.execute(
            """
            INSERT INTO skills (
                skill_name, category, description, source, skill_dir, skill_path,
                tags_json, aliases_json, enabled, pinned, hidden_from_prompt,
                created_at, updated_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(skill_name) DO UPDATE SET
                category=excluded.category,
                description=excluded.description,
                source=excluded.source,
                skill_dir=COALESCE(excluded.skill_dir, skills.skill_dir),
                skill_path=COALESCE(excluded.skill_path, skills.skill_path),
                tags_json=excluded.tags_json,
                aliases_json=excluded.aliases_json,
                enabled=COALESCE(excluded.enabled, skills.enabled),
                pinned=excluded.pinned,
                hidden_from_prompt=excluded.hidden_from_prompt,
                updated_at=excluded.updated_at,
                last_seen_at=excluded.last_seen_at
            """,
            (
                payload["skill_name"],
                payload["category"],
                payload["description"],
                payload["source"],
                payload["skill_dir"],
                payload["skill_path"],
                payload["tags_json"],
                payload["aliases_json"],
                payload["enabled"],
                payload["pinned"],
                payload["hidden_from_prompt"],
                payload["created_at"],
                payload["updated_at"],
                payload["last_seen_at"],
            ),
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO skill_usage_rollups(skill_name) VALUES (?)",
            (payload["skill_name"],),
        )
        self._conn.commit()

    def set_enabled(self, skill_name: str, enabled: bool) -> None:
        self._conn.execute(
            "UPDATE skills SET enabled=?, updated_at=? WHERE skill_name=?",
            (int(bool(enabled)), time.time(), str(skill_name)),
        )
        self._conn.commit()

    def mark_missing_skills(self, seen_names: set[str]) -> None:
        if not seen_names:
            return
        placeholders = ",".join("?" for _ in seen_names)
        self._conn.execute(
            f"UPDATE skills SET last_seen_at=? WHERE skill_name IN ({placeholders})",
            (time.time(), *sorted(seen_names)),
        )
        self._conn.commit()

    def get_skill(self, skill_name: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT s.*, r.total_count, r.last_used_at, r.used_30d, r.used_90d,
                   r.used_discord_90d, r.used_cli_90d
            FROM skills s
            LEFT JOIN skill_usage_rollups r ON r.skill_name = s.skill_name
            WHERE s.skill_name = ?
            """,
            (str(skill_name),),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def record_usage(
        self,
        *,
        skill_name: str,
        session_id: str | None = None,
        platform: str | None = None,
        trigger: str,
        used_at: float | None = None,
    ) -> None:
        when = float(used_at or time.time())
        if self.get_skill(skill_name) is None:
            self.upsert_skill({"skill_name": skill_name, "source": "local"})
        self._conn.execute(
            "INSERT INTO skill_usage_events(skill_name, used_at, session_id, platform, trigger) VALUES (?, ?, ?, ?, ?)",
            (str(skill_name), when, _normalize_text(session_id), _normalize_text(platform), str(trigger)),
        )
        self._conn.commit()
        self.rebuild_rollups(skill_name=str(skill_name))

    def rebuild_rollups(self, skill_name: str | None = None) -> None:
        now = time.time()
        cutoff_30 = now - (30 * 24 * 60 * 60)
        cutoff_90 = now - (90 * 24 * 60 * 60)
        if skill_name:
            names = [skill_name]
        else:
            names = [row[0] for row in self._conn.execute("SELECT skill_name FROM skills").fetchall()]
        for name in names:
            stats = self._conn.execute(
                """
                SELECT
                    COUNT(*) AS total_count,
                    MAX(used_at) AS last_used_at,
                    SUM(CASE WHEN used_at >= ? THEN 1 ELSE 0 END) AS used_30d,
                    SUM(CASE WHEN used_at >= ? THEN 1 ELSE 0 END) AS used_90d,
                    SUM(CASE WHEN used_at >= ? AND platform = 'discord' THEN 1 ELSE 0 END) AS used_discord_90d,
                    SUM(CASE WHEN used_at >= ? AND platform = 'cli' THEN 1 ELSE 0 END) AS used_cli_90d
                FROM skill_usage_events
                WHERE skill_name = ?
                """,
                (cutoff_30, cutoff_90, cutoff_90, cutoff_90, name),
            ).fetchone()
            self._conn.execute(
                """
                INSERT INTO skill_usage_rollups (
                    skill_name, total_count, last_used_at, used_30d, used_90d,
                    used_discord_90d, used_cli_90d
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(skill_name) DO UPDATE SET
                    total_count=excluded.total_count,
                    last_used_at=excluded.last_used_at,
                    used_30d=excluded.used_30d,
                    used_90d=excluded.used_90d,
                    used_discord_90d=excluded.used_discord_90d,
                    used_cli_90d=excluded.used_cli_90d
                """,
                (
                    name,
                    int(stats["total_count"] or 0),
                    stats["last_used_at"],
                    int(stats["used_30d"] or 0),
                    int(stats["used_90d"] or 0),
                    int(stats["used_discord_90d"] or 0),
                    int(stats["used_cli_90d"] or 0),
                ),
            )
        self._conn.commit()

    def search_skills(
        self,
        query: str | None,
        *,
        include_disabled: bool = False,
        limit: int = 20,
        allowed_skill_names: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._fetch_rows(include_disabled=include_disabled, allowed_skill_names=allowed_skill_names)
        scored = self._score_rows(rows, query)
        return scored[: max(1, int(limit))]

    def get_prompt_candidates(
        self,
        *,
        user_message: str | None,
        limit: int = 10,
        allowed_skill_names: set[str] | None = None,
        pinned_names: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._fetch_rows(include_disabled=False, allowed_skill_names=allowed_skill_names)
        pinned = {str(name).strip() for name in (pinned_names or []) if str(name).strip()}
        scored = self._score_rows(rows, user_message, pinned_names=pinned, require_match=bool(user_message))
        return scored[: max(1, int(limit))]

    def _fetch_rows(
        self,
        *,
        include_disabled: bool,
        allowed_skill_names: set[str] | None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT s.*, r.total_count, r.last_used_at, r.used_30d, r.used_90d,
                   r.used_discord_90d, r.used_cli_90d
            FROM skills s
            LEFT JOIN skill_usage_rollups r ON r.skill_name = s.skill_name
        """
        rows = [dict(row) for row in self._conn.execute(sql).fetchall()]
        filtered: list[dict[str, Any]] = []
        for row in rows:
            if not include_disabled and not bool(row.get("enabled", 1)):
                continue
            if allowed_skill_names is not None and row["skill_name"] not in allowed_skill_names:
                continue
            filtered.append(row)
        return filtered

    def _score_rows(
        self,
        rows: Iterable[dict[str, Any]],
        query: str | None,
        *,
        pinned_names: set[str] | None = None,
        require_match: bool = False,
    ) -> list[dict[str, Any]]:
        pinned = pinned_names or set()
        query_text = str(query or "").strip().lower()
        terms = _tokenize(query_text)
        cjk_chunks = _extract_cjk_chunks(query_text)
        scored: list[dict[str, Any]] = []
        for row in rows:
            haystacks = [
                str(row.get("skill_name") or "").lower(),
                str(row.get("category") or "").lower(),
                str(row.get("description") or "").lower(),
                str(row.get("tags_json") or "").lower(),
                str(row.get("aliases_json") or "").lower(),
            ]
            score = 0.0
            for term in terms:
                if term in haystacks[0]:
                    score += 12
                if term in haystacks[1]:
                    score += 3
                if term in haystacks[2]:
                    score += 6
                if term in haystacks[3]:
                    score += 4
                if term in haystacks[4]:
                    score += 5

            if query_text:
                if query_text in haystacks[0]:
                    score += 18
                if query_text in haystacks[2]:
                    score += 12
                if query_text in haystacks[3]:
                    score += 8
                if query_text in haystacks[4]:
                    score += 10

            for chunk in cjk_chunks:
                if chunk in haystacks[0]:
                    score += 10
                if chunk in haystacks[2]:
                    score += 8
                if chunk in haystacks[3]:
                    score += 6
                if chunk in haystacks[4]:
                    score += 7

            if row.get("skill_name") in pinned or bool(row.get("pinned")):
                score += 100
            score += min(int(row.get("total_count") or 0), 20) * 0.5
            row["score"] = score
            row["enabled"] = bool(row.get("enabled", 1))
            if require_match and not score and row.get("skill_name") not in pinned and not bool(row.get("pinned")):
                continue
            scored.append(row)
        scored.sort(
            key=lambda row: (
                row.get("score", 0),
                int(row.get("pinned") or 0),
                int(row.get("total_count") or 0),
                row.get("skill_name") or "",
            ),
            reverse=True,
        )
        return scored


def _tokenize(query: str | None) -> list[str]:
    if not query:
        return []

    normalized = str(query).strip().lower()
    if not normalized:
        return []

    tokens: list[str] = [token for token in _TOKEN_RE.findall(normalized) if token]
    for chunk in _extract_cjk_chunks(normalized):
        tokens.append(chunk)
        for n in (3, 2):
            if len(chunk) < n:
                continue
            for idx in range(len(chunk) - n + 1):
                tokens.append(chunk[idx: idx + n])

    return _dedupe_preserve_order(tokens)[:_MAX_TOKENS]


def _extract_cjk_chunks(text: str) -> list[str]:
    return [chunk for chunk in _CJK_CHUNK_RE.findall(text) if chunk]


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _json_dumps(values: Sequence[str]) -> str:
    import json

    return json.dumps([str(v).strip() for v in values if str(v).strip()], ensure_ascii=False)
