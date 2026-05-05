"""SQLite-backed skill index with SudachiPy + multilingual-e5-base scoring.

スキーマ刷新（2026-05-05）:
  - description 2層化: description（30文字以内・注入用）/ description_full（制限なし・スコアリング用）
  - vector / vector_model カラム追加（multilingual-e5-base）
  - 廃止: source / skill_path / tags_json / aliases_json / triggers_json
  - スコアリング: SudachiPy語幹マッチ + e5ベクトル類似度 × 30（使用頻度除外）
  - pinned枠（最大4件）と動的枠（6件）を完全分離
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SudachiPy setup (optional — falls back gracefully if unavailable)
# ---------------------------------------------------------------------------

_STOP_POS = {"助詞", "助動詞", "記号", "補助記号"}
_sudachi_tokenizer = None
_sudachi_init_tried = False


def _get_sudachi_tokenizer():
    global _sudachi_tokenizer, _sudachi_init_tried
    if _sudachi_init_tried:
        return _sudachi_tokenizer
    _sudachi_init_tried = True
    try:
        import sudachipy
        import sudachidict_small  # noqa: F401 — registers the small dict
        _sudachi_tokenizer = sudachipy.Dictionary(dict="small").create()
    except Exception as e:
        logger.debug("SudachiPy unavailable (fallback to simple tokenizer): %s", e)
    return _sudachi_tokenizer


def stem_tokenize(text: str) -> list[str]:
    """テキストをSudachiPyで語幹トークン化。unavailableなら空白分割で代替。"""
    tokenizer = _get_sudachi_tokenizer()
    if tokenizer is None:
        import re
        tokens = re.findall(r"[a-zA-Z0-9_-]+|[぀-鿿＀-￯]+", text)
        return list(dict.fromkeys(tokens))

    morphemes = tokenizer.tokenize(text)
    stems = []
    seen = set()
    for m in morphemes:
        pos = m.part_of_speech()[0]
        if pos in _STOP_POS:
            continue
        s = m.dictionary_form()
        if s and s not in seen:
            stems.append(s)
            seen.add(s)
    return stems


# ---------------------------------------------------------------------------
# E5 embedding (optional — lazy load, cached singleton)
# ---------------------------------------------------------------------------

_e5_model = None
_e5_init_tried = False
_E5_MODEL_NAME = "intfloat/multilingual-e5-base"


def _get_e5_model():
    global _e5_model, _e5_init_tried
    if _e5_init_tried:
        return _e5_model
    _e5_init_tried = True
    try:
        from sentence_transformers import SentenceTransformer
        _e5_model = SentenceTransformer(_E5_MODEL_NAME)
        logger.debug("multilingual-e5-base loaded")
    except Exception as e:
        logger.debug("sentence-transformers unavailable: %s", e)
    return _e5_model


def encode_passage(text: str) -> "bytes | None":
    """description_full をベクトル化（passage: プレフィックス付き）。失敗時はNone。"""
    model = _get_e5_model()
    if model is None:
        return None
    try:
        import numpy as np
        vec = model.encode("passage: " + text, normalize_embeddings=True)
        return vec.astype(np.float32).tobytes()
    except Exception as e:
        logger.debug("encode_passage failed: %s", e)
        return None


def encode_query_stems(stems: list[str]) -> "Any | None":
    """語幹リストをベクトル化（query: プレフィックス付き）。失敗時はNone。"""
    model = _get_e5_model()
    if model is None:
        return None
    try:
        import numpy as np  # noqa: F401 (used via model.encode)
        text = " ".join(stems)
        return model.encode("query: " + text, normalize_embeddings=True)
    except Exception as e:
        logger.debug("encode_query_stems failed: %s", e)
        return None


def cosine_score(query_vec: Any, skill_vec_bytes: bytes) -> float:
    """コサイン類似度を 0.0〜1.0 に正規化して返す。"""
    try:
        import numpy as np
        sv = np.frombuffer(skill_vec_bytes, dtype=np.float32)
        if sv.shape != query_vec.shape or not sv.any():
            return 0.0
        cos = float(np.dot(query_vec, sv) / (
            np.linalg.norm(query_vec) * np.linalg.norm(sv) + 1e-8
        ))
        return (cos + 1.0) / 2.0
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS skills (
    skill_name         TEXT PRIMARY KEY,
    category           TEXT NOT NULL DEFAULT 'general',
    description        TEXT NOT NULL DEFAULT '',
    description_full   TEXT NOT NULL DEFAULT '',
    skill_dir          TEXT NOT NULL DEFAULT '',
    vector             BLOB,
    vector_model       TEXT,
    enabled            INTEGER NOT NULL DEFAULT 1,
    pinned             INTEGER NOT NULL DEFAULT 0,
    hidden_from_prompt INTEGER NOT NULL DEFAULT 0,
    created_at         REAL NOT NULL,
    updated_at         REAL NOT NULL,
    last_seen_at       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_usage_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    used_at    REAL NOT NULL,
    session_id TEXT,
    platform   TEXT,
    FOREIGN KEY (skill_name) REFERENCES skills(skill_name)
);

CREATE INDEX IF NOT EXISTS idx_skill_usage_events_skill_used_at
    ON skill_usage_events(skill_name, used_at DESC);

CREATE TABLE IF NOT EXISTS skill_usage_rollups (
    skill_name   TEXT PRIMARY KEY,
    total_count  INTEGER NOT NULL DEFAULT 0,
    last_used_at REAL,
    used_30d     INTEGER NOT NULL DEFAULT 0,
    used_90d     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (skill_name) REFERENCES skills(skill_name)
);
"""


def get_skill_index_db_path(skills_dir: "Path | None" = None) -> Path:
    if skills_dir is not None:
        return Path(skills_dir).resolve().parent / "skill_index.db"
    return get_hermes_home() / "skill_index.db"


# ---------------------------------------------------------------------------
# SkillIndexDB
# ---------------------------------------------------------------------------

MIN_DYNAMIC_SCORE = 10.0
PINNED_LIMIT = 4
DYNAMIC_LIMIT = 6


class SkillIndexDB:
    def __init__(self, db_path: "str | Path | None" = None):
        self.db_path = Path(db_path) if db_path else get_skill_index_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate_schema()
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def _migrate_schema(self) -> None:
        """旧スキーマから新スキーマへのマイグレーション。"""
        cur = self._conn.execute("PRAGMA table_info(skills)")
        rows = cur.fetchall()
        existing = {row["name"] for row in rows}
        if not existing:
            return

        # 旧カラムの NOT NULL 制約を緩和（source は旧スキーマで NOT NULL だった）
        # SQLite は ALTER COLUMN 不可のため、source が NOT NULL なら DEFAULT 値で埋める
        source_info = next((r for r in rows if r["name"] == "source"), None)
        if source_info and source_info["notnull"] and source_info["dflt_value"] is None:
            try:
                self._conn.execute("UPDATE skills SET source='local' WHERE source IS NULL OR source=''")
            except Exception as e:
                logger.debug("source backfill skipped: %s", e)

        add_cols = []
        if "description_full" not in existing:
            add_cols.append("ALTER TABLE skills ADD COLUMN description_full TEXT NOT NULL DEFAULT ''")
        if "vector" not in existing:
            add_cols.append("ALTER TABLE skills ADD COLUMN vector BLOB")
        if "vector_model" not in existing:
            add_cols.append("ALTER TABLE skills ADD COLUMN vector_model TEXT")
        if "skill_dir" not in existing:
            add_cols.append("ALTER TABLE skills ADD COLUMN skill_dir TEXT NOT NULL DEFAULT ''")

        for stmt in add_cols:
            sp = "sp_migrate_" + stmt[len("ALTER TABLE skills ADD COLUMN "):].split()[0]
            try:
                self._conn.execute(f"SAVEPOINT {sp}")
                self._conn.execute(stmt)
                self._conn.execute(f"RELEASE {sp}")
            except sqlite3.OperationalError as e:
                self._conn.execute(f"ROLLBACK TO {sp}")
                self._conn.execute(f"RELEASE {sp}")
                logger.debug("Migration skipped (%s): %s", stmt[:60], e)

        if "description_full" not in existing:
            self._conn.execute(
                "UPDATE skills SET description_full = description "
                "WHERE description_full = '' AND description != ''"
            )

        self._conn.commit()

    def _has_legacy_source_col(self) -> bool:
        """旧スキーマの source カラムが NOT NULL かどうかを返す（upsert 時の分岐に使う）。"""
        cur = self._conn.execute("PRAGMA table_info(skills)")
        for row in cur.fetchall():
            if row["name"] == "source" and row["notnull"]:
                return True
        return False

    def close(self) -> None:
        self._conn.close()

    def _normalize_skill_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        now = float(metadata.get("now") or time.time())
        name = str(metadata.get("skill_name") or metadata.get("name") or "").strip()
        desc = _normalize_text(metadata.get("description")) or ""
        desc_full = _normalize_text(metadata.get("description_full")) or desc
        skill_dir = _normalize_text(metadata.get("skill_dir")) or ""
        return {
            "skill_name": name,
            "category": _normalize_text(metadata.get("category")) or "general",
            "description": desc,
            "description_full": desc_full,
            "skill_dir": skill_dir,
            "source": _normalize_text(metadata.get("source")) or "local",  # 旧スキーマ互換
            "enabled": int(bool(metadata.get("enabled", True))),
            "pinned": int(bool(metadata.get("pinned", False))),
            "hidden_from_prompt": int(bool(metadata.get("hidden_from_prompt", False))),
            "created_at": now,
            "updated_at": now,
            "last_seen_at": now,
        }

    def upsert_skill(self, metadata: dict[str, Any]) -> None:
        # Hermes Agent はシングルスレッドで動作するため TOCTOU 競合は実害なし。
        # マルチスレッド化が必要になった場合は SELECT→INSERT/UPDATE を
        # INSERT OR REPLACE の1ステップに統合すること。
        payload = self._normalize_skill_payload(metadata)
        if not payload["skill_name"]:
            raise ValueError("skill_name is required")

        vec_bytes: "bytes | None" = None
        vec_model: "str | None" = None
        if payload["description_full"]:
            existing = self._conn.execute(
                "SELECT vector_model FROM skills WHERE skill_name=?", (payload["skill_name"],)
            ).fetchone()
            if existing is None or existing["vector_model"] != _E5_MODEL_NAME:
                vec_bytes = encode_passage(payload["description_full"])
                if vec_bytes is not None:
                    vec_model = _E5_MODEL_NAME

        has_source = self._has_legacy_source_col()

        if vec_bytes is not None:
            if has_source:
                self._conn.execute(
                    """
                    INSERT INTO skills (
                        skill_name, category, description, description_full, skill_dir,
                        source, vector, vector_model, enabled, pinned, hidden_from_prompt,
                        created_at, updated_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(skill_name) DO UPDATE SET
                        category=excluded.category,
                        description=excluded.description,
                        description_full=excluded.description_full,
                        skill_dir=COALESCE(NULLIF(excluded.skill_dir,''), skills.skill_dir),
                        vector=excluded.vector,
                        vector_model=excluded.vector_model,
                        enabled=excluded.enabled,
                        pinned=excluded.pinned,
                        hidden_from_prompt=excluded.hidden_from_prompt,
                        updated_at=excluded.updated_at,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        payload["skill_name"], payload["category"], payload["description"],
                        payload["description_full"], payload["skill_dir"],
                        payload["source"], vec_bytes, vec_model,
                        payload["enabled"], payload["pinned"], payload["hidden_from_prompt"],
                        payload["created_at"], payload["updated_at"], payload["last_seen_at"],
                    ),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO skills (
                        skill_name, category, description, description_full, skill_dir,
                        vector, vector_model, enabled, pinned, hidden_from_prompt,
                        created_at, updated_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(skill_name) DO UPDATE SET
                        category=excluded.category,
                        description=excluded.description,
                        description_full=excluded.description_full,
                        skill_dir=COALESCE(NULLIF(excluded.skill_dir,''), skills.skill_dir),
                        vector=excluded.vector,
                        vector_model=excluded.vector_model,
                        enabled=excluded.enabled,
                        pinned=excluded.pinned,
                        hidden_from_prompt=excluded.hidden_from_prompt,
                        updated_at=excluded.updated_at,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        payload["skill_name"], payload["category"], payload["description"],
                        payload["description_full"], payload["skill_dir"],
                        vec_bytes, vec_model,
                        payload["enabled"], payload["pinned"], payload["hidden_from_prompt"],
                        payload["created_at"], payload["updated_at"], payload["last_seen_at"],
                    ),
                )
        else:
            if has_source:
                self._conn.execute(
                    """
                    INSERT INTO skills (
                        skill_name, category, description, description_full, skill_dir,
                        source, enabled, pinned, hidden_from_prompt,
                        created_at, updated_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(skill_name) DO UPDATE SET
                        category=excluded.category,
                        description=excluded.description,
                        description_full=excluded.description_full,
                        skill_dir=COALESCE(NULLIF(excluded.skill_dir,''), skills.skill_dir),
                        enabled=excluded.enabled,
                        pinned=excluded.pinned,
                        hidden_from_prompt=excluded.hidden_from_prompt,
                        updated_at=excluded.updated_at,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        payload["skill_name"], payload["category"], payload["description"],
                        payload["description_full"], payload["skill_dir"],
                        payload["source"],
                        payload["enabled"], payload["pinned"], payload["hidden_from_prompt"],
                        payload["created_at"], payload["updated_at"], payload["last_seen_at"],
                    ),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO skills (
                        skill_name, category, description, description_full, skill_dir,
                        enabled, pinned, hidden_from_prompt,
                        created_at, updated_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(skill_name) DO UPDATE SET
                        category=excluded.category,
                        description=excluded.description,
                        description_full=excluded.description_full,
                        skill_dir=COALESCE(NULLIF(excluded.skill_dir,''), skills.skill_dir),
                        enabled=excluded.enabled,
                        pinned=excluded.pinned,
                        hidden_from_prompt=excluded.hidden_from_prompt,
                        updated_at=excluded.updated_at,
                        last_seen_at=excluded.last_seen_at
                    """,
                    (
                        payload["skill_name"], payload["category"], payload["description"],
                        payload["description_full"], payload["skill_dir"],
                        payload["enabled"], payload["pinned"], payload["hidden_from_prompt"],
                        payload["created_at"], payload["updated_at"], payload["last_seen_at"],
                    ),
                )

        self._conn.execute(
            "INSERT OR IGNORE INTO skill_usage_rollups(skill_name) VALUES (?)",
            (payload["skill_name"],),
        )
        self._conn.commit()


    def upsert_skills_batch(self, entries: "list[dict[str, Any]]") -> int:
        """差分チェック付きバッチupsert。変更のあったスキルのみ upsert_skill() を呼ぶ。

        G3（毎リクエスト全件upsert）と G10（snapshotヒット時の乖離）を同時解決。
        - 全件を1 SELECT で取得してキャッシュを構築
        - vector_model 一致 かつ description_full 一致のスキルはスキップ
        - 差分ありのスキルのみ upsert_skill() を実行
        返り値: upsert した件数
        """
        if not entries:
            return 0

        names = [str(e.get("skill_name") or e.get("name") or "").strip() for e in entries]
        names = [n for n in names if n]
        if not names:
            return 0

        placeholders = ",".join("?" for _ in names)
        rows = self._conn.execute(
            f"SELECT skill_name, description_full, vector_model FROM skills WHERE skill_name IN ({placeholders})",
            names,
        ).fetchall()
        existing: dict[str, tuple[str, str | None]] = {
            row["skill_name"]: (row["description_full"] or "", row["vector_model"])
            for row in rows
        }

        count = 0
        for entry in entries:
            name = str(entry.get("skill_name") or entry.get("name") or "").strip()
            if not name:
                continue
            desc_full = str(entry.get("description_full") or entry.get("description") or "").strip()
            if name in existing:
                ex_desc, ex_model = existing[name]
                if ex_model == _E5_MODEL_NAME and ex_desc == desc_full:
                    continue
            self.upsert_skill(entry)
            count += 1

        return count

    def delete_skill(self, skill_name: str) -> bool:
        """DBからスキルレコードとその使用履歴を削除する。存在すれば True を返す。"""
        existing = self._conn.execute(
            "SELECT 1 FROM skills WHERE skill_name=?", (str(skill_name),)
        ).fetchone()
        if existing is None:
            return False
        self._conn.execute(
            "DELETE FROM skill_usage_events WHERE skill_name=?", (str(skill_name),)
        )
        self._conn.execute(
            "DELETE FROM skill_usage_rollups WHERE skill_name=?", (str(skill_name),)
        )
        self._conn.execute(
            "DELETE FROM skills WHERE skill_name=?", (str(skill_name),)
        )
        self._conn.commit()
        return True

    def set_enabled(self, skill_name: str, enabled: bool) -> None:
        self._conn.execute(
            "UPDATE skills SET enabled=?, updated_at=? WHERE skill_name=?",
            (int(bool(enabled)), time.time(), str(skill_name)),
        )
        self._conn.commit()


    def delete_skills_not_in(self, seen_names: "set[str]") -> int:
        """ファイルシステムに存在しないスキル（ゾンビ行）をDBから削除する。

        G11（リネーム・移動後のゾンビ行）対策。
        SKILL.md が正データであるため、seen_names に含まれないスキルを削除する。
        使用履歴（skill_usage_events/rollups）も連鎖削除。
        返り値: 削除した件数
        """
        if not seen_names:
            return 0
        placeholders = ",".join("?" for _ in seen_names)
        zombies = self._conn.execute(
            f"SELECT skill_name FROM skills WHERE skill_name NOT IN ({placeholders})",
            sorted(seen_names),
        ).fetchall()
        count = 0
        for row in zombies:
            self.delete_skill(row["skill_name"])
            count += 1
        if count:
            logger.debug("delete_skills_not_in: %d zombie row(s) deleted", count)
        return count

    def mark_missing_skills(self, seen_names: set[str]) -> None:
        if not seen_names:
            return
        placeholders = ",".join("?" for _ in seen_names)
        self._conn.execute(
            f"UPDATE skills SET last_seen_at=? WHERE skill_name IN ({placeholders})",
            (time.time(), *sorted(seen_names)),
        )
        self._conn.commit()

    def get_skill(self, skill_name: str) -> "dict[str, Any] | None":
        row = self._conn.execute(
            """
            SELECT s.*, r.total_count, r.last_used_at, r.used_30d, r.used_90d
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
        session_id: "str | None" = None,
        platform: "str | None" = None,
        used_at: "float | None" = None,
        trigger: "str | None" = None,  # 旧APIとの互換性のため受け入れるが無視
    ) -> None:
        when = float(used_at or time.time())
        if self.get_skill(skill_name) is None:
            self.upsert_skill({"skill_name": skill_name})
        self._conn.execute(
            "INSERT INTO skill_usage_events(skill_name, used_at, session_id, platform) VALUES (?, ?, ?, ?)",
            (str(skill_name), when, _normalize_text(session_id), _normalize_text(platform)),
        )
        self._conn.commit()
        self.rebuild_rollups(skill_name=str(skill_name))

    def rebuild_rollups(self, skill_name: "str | None" = None) -> None:
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
                    SUM(CASE WHEN used_at >= ? THEN 1 ELSE 0 END) AS used_90d
                FROM skill_usage_events
                WHERE skill_name = ?
                """,
                (cutoff_30, cutoff_90, name),
            ).fetchone()
            self._conn.execute(
                """
                INSERT INTO skill_usage_rollups (
                    skill_name, total_count, last_used_at, used_30d, used_90d
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(skill_name) DO UPDATE SET
                    total_count=excluded.total_count,
                    last_used_at=excluded.last_used_at,
                    used_30d=excluded.used_30d,
                    used_90d=excluded.used_90d
                """,
                (
                    name,
                    int(stats["total_count"] or 0),
                    stats["last_used_at"],
                    int(stats["used_30d"] or 0),
                    int(stats["used_90d"] or 0),
                ),
            )
        self._conn.commit()

    def search_skills(
        self,
        query: "str | None",
        *,
        include_disabled: bool = False,
        limit: int = 20,
        allowed_skill_names: "set[str] | None" = None,
    ) -> "list[dict[str, Any]]":
        rows = self._fetch_rows(include_disabled=include_disabled, allowed_skill_names=allowed_skill_names)
        scored = self._score_rows(rows, query)
        return scored[: max(1, int(limit))]

    def get_prompt_candidates(
        self,
        *,
        user_message: "str | None",
        limit: int = 10,
        allowed_skill_names: "set[str] | None" = None,
        pinned_names: "Sequence[str] | None" = None,
    ) -> "list[dict[str, Any]]":
        """pinned枠（最大4件）と動的枠（最大6件）を分離して抽出する。"""
        rows = self._fetch_rows(include_disabled=False, allowed_skill_names=allowed_skill_names)

        config_pinned = {str(n).strip() for n in (pinned_names or []) if str(n).strip()}
        for row in rows:
            if row["skill_name"] in config_pinned:
                row["pinned"] = 1

        scored = self._score_rows(rows, user_message)

        pinned_rows = [r for r in scored if r.get("pinned")]
        pinned_top = pinned_rows[:PINNED_LIMIT]

        dynamic_rows = [
            r for r in scored
            if not r.get("pinned") and r.get("score", 0) >= MIN_DYNAMIC_SCORE
        ]
        dynamic_top = dynamic_rows[:DYNAMIC_LIMIT]

        return pinned_top + dynamic_top

    def _fetch_rows(
        self,
        *,
        include_disabled: bool,
        allowed_skill_names: "set[str] | None",
    ) -> "list[dict[str, Any]]":
        sql = """
            SELECT s.*, r.total_count, r.last_used_at, r.used_30d, r.used_90d
            FROM skills s
            LEFT JOIN skill_usage_rollups r ON r.skill_name = s.skill_name
        """
        rows = [dict(row) for row in self._conn.execute(sql).fetchall()]
        filtered: "list[dict[str, Any]]" = []
        for row in rows:
            if not include_disabled and not bool(row.get("enabled", 1)):
                continue
            if allowed_skill_names is not None and row["skill_name"] not in allowed_skill_names:
                continue
            filtered.append(row)
        return filtered

    def _score_rows(
        self,
        rows: "Iterable[dict[str, Any]]",
        query: "str | None",
    ) -> "list[dict[str, Any]]":
        """SudachiPy語幹マッチ + e5ベクトル類似度でスコアリング。"""
        query_text = str(query or "").strip()
        stems = stem_tokenize(query_text) if query_text else []
        query_vec = encode_query_stems(stems) if stems else None

        scored: "list[dict[str, Any]]" = []
        for row in rows:
            desc_full = str(row.get("description_full") or row.get("description") or "")
            desc_lower = desc_full.lower()

            stem_score = 0.0
            for stem in stems:
                count = desc_lower.count(stem.lower())
                if count > 0:
                    stem_score += 6.0 * min(count, 3)

            vec_score = 0.0
            skill_vec = row.get("vector")
            if query_vec is not None and skill_vec is not None:
                vec_score = cosine_score(query_vec, skill_vec) * 30.0

            row["score"] = stem_score + vec_score
            row["enabled"] = bool(row.get("enabled", 1))
            scored.append(row)

        scored.sort(key=lambda r: r.get("score", 0), reverse=True)
        return scored


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_text(value: Any) -> "str | None":
    if value is None:
        return None
    text = str(value).strip()
    return text or None
