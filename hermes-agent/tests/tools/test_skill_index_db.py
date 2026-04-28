import sqlite3

from tools.skill_index_db import SkillIndexDB, _tokenize


def test_upsert_and_search_skills(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")

    db.upsert_skill(
        {
            "skill_name": "python-debug",
            "category": "coding",
            "description": "Debug Python scripts",
            "source": "builtin",
            "tags": ["python", "debugging"],
            "skill_dir": "/tmp/skills/coding/python-debug",
            "skill_path": "/tmp/skills/coding/python-debug/SKILL.md",
        }
    )
    db.upsert_skill(
        {
            "skill_name": "powerpoint",
            "category": "productivity",
            "description": "Work with slide decks",
            "source": "builtin",
            "tags": ["slides", "pptx"],
            "skill_dir": "/tmp/skills/productivity/powerpoint",
            "skill_path": "/tmp/skills/productivity/powerpoint/SKILL.md",
        }
    )

    result = db.search_skills("debug", include_disabled=False, limit=10)
    assert result[0]["skill_name"] == "python-debug"
    assert result[0]["description"] == "Debug Python scripts"


def test_record_usage_updates_rollups(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill(
        {
            "skill_name": "python-debug",
            "category": "coding",
            "description": "Debug Python scripts",
            "source": "builtin",
            "tags": ["python"],
        }
    )

    db.record_usage(
        skill_name="python-debug",
        session_id="sess-1",
        platform="discord",
        trigger="skill_view",
    )

    summary = db.get_skill("python-debug")
    assert summary is not None
    assert summary["total_count"] == 1
    assert summary["last_used_at"] is not None


def test_prompt_candidates_prioritize_relevant_and_pinned_skills(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill(
        {
            "skill_name": "hermes-agent",
            "category": "autonomous-ai-agents",
            "description": "Hermes configuration and usage",
            "source": "builtin",
            "tags": ["hermes", "config"],
            "pinned": True,
        }
    )
    db.upsert_skill(
        {
            "skill_name": "python-debug",
            "category": "coding",
            "description": "Debug Python scripts",
            "source": "builtin",
            "tags": ["python", "debugging"],
        }
    )
    db.upsert_skill(
        {
            "skill_name": "powerpoint",
            "category": "productivity",
            "description": "Work with slide decks",
            "source": "builtin",
            "tags": ["slides", "pptx"],
        }
    )

    candidates = db.get_prompt_candidates(
        user_message="Please debug this python script",
        limit=5,
    )

    names = [row["skill_name"] for row in candidates]
    assert "hermes-agent" in names
    assert "python-debug" in names
    assert "powerpoint" not in names


def test_tokenize_extracts_cjk_terms():
    tokens = _tokenize("日本語のスキル検索を改善したい")

    assert tokens
    assert any("スキル" in token for token in tokens)
    assert any(len(token) >= 2 for token in tokens)


def test_prompt_candidates_support_japanese_queries(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill(
        {
            "skill_name": "python-debug-ja",
            "category": "coding",
            "description": "Pythonのデバッグと不具合調査",
            "source": "builtin",
            "tags": ["python", "デバッグ", "不具合"],
        }
    )
    db.upsert_skill(
        {
            "skill_name": "powerpoint-ja",
            "category": "productivity",
            "description": "スライド資料を編集する",
            "source": "builtin",
            "tags": ["slides", "pptx"],
        }
    )

    candidates = db.get_prompt_candidates(
        user_message="このPython不具合をデバッグしたい",
        limit=5,
    )

    names = [row["skill_name"] for row in candidates]
    assert "python-debug-ja" in names
    assert "powerpoint-ja" not in names



def test_set_enabled_updates_state(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill(
        {
            "skill_name": "python-debug",
            "category": "coding",
            "description": "Debug Python scripts",
            "source": "builtin",
        }
    )

    db.set_enabled("python-debug", False)
    row = db.get_skill("python-debug")
    assert row["enabled"] == 0

    db.set_enabled("python-debug", True)
    row = db.get_skill("python-debug")
    assert row["enabled"] == 1


def test_disabled_skills_are_excluded_from_default_search(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill(
        {
            "skill_name": "python-debug",
            "category": "coding",
            "description": "Debug Python scripts",
            "source": "builtin",
        }
    )
    db.set_enabled("python-debug", False)

    assert db.search_skills("python", include_disabled=False, limit=10) == []
    assert db.search_skills("python", include_disabled=True, limit=10)[0]["skill_name"] == "python-debug"
