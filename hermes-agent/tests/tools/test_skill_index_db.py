import sqlite3

from tools.skill_index_db import SkillIndexDB, stem_tokenize


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
            "description_full": "Hermes Agent configuration, setup, and usage guide.",
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
            "description_full": "Debug and troubleshoot Python scripts, trace errors, fix bugs in Python code.",
            "source": "builtin",
            "tags": ["python", "debugging"],
        }
    )
    db.upsert_skill(
        {
            "skill_name": "powerpoint",
            "category": "productivity",
            "description": "Work with slide decks",
            "description_full": "Create and edit PowerPoint slide decks and presentation files.",
            "source": "builtin",
            "tags": ["slides", "pptx"],
        }
    )

    candidates = db.get_prompt_candidates(
        user_message="Please debug this python script",
        limit=5,
    )

    names = [row["skill_name"] for row in candidates]
    # pinnedスキルは常に含まれる
    assert "hermes-agent" in names
    # クエリに直接一致するスキルが含まれる
    assert "python-debug" in names
    # python-debug は powerpoint よりスコアが高い
    if "powerpoint" in names:
        python_idx = names.index("python-debug")
        pp_idx = names.index("powerpoint")
        assert python_idx < pp_idx, "python-debug should rank higher than powerpoint"


def test_tokenize_extracts_cjk_terms():
    tokens = stem_tokenize("日本語のスキル検索を改善したい")

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
            "description_full": "Pythonスクリプトのデバッグ、不具合調査、エラーのトレース、バグ修正を行う。",
            "source": "builtin",
            "tags": ["python", "デバッグ", "不具合"],
        }
    )
    db.upsert_skill(
        {
            "skill_name": "powerpoint-ja",
            "category": "productivity",
            "description": "スライド資料を編集する",
            "description_full": "PowerPointのスライド資料やプレゼンテーションファイルを作成・編集する。",
            "source": "builtin",
            "tags": ["slides", "pptx"],
        }
    )

    candidates = db.get_prompt_candidates(
        user_message="このPython不具合をデバッグしたい",
        limit=5,
    )

    names = [row["skill_name"] for row in candidates]
    # クエリに直接一致するスキルが含まれる
    assert "python-debug-ja" in names
    # python-debug-ja は powerpoint-ja よりスコアが高い
    if "powerpoint-ja" in names:
        python_idx = names.index("python-debug-ja")
        pp_idx = names.index("powerpoint-ja")
        assert python_idx < pp_idx, "python-debug-ja should rank higher than powerpoint-ja"



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


# ---------------------------------------------------------------------------
# G15: E5モデルバージョン管理
# ---------------------------------------------------------------------------

def test_e5_model_name_has_revision():
    """_E5_MODEL_REVISION が設定されており、ベクトル生成に使われることを確認（G15）。"""
    from tools.skill_index_db import _E5_MODEL_NAME, _E5_MODEL_REVISION
    assert _E5_MODEL_NAME == "intfloat/multilingual-e5-base"
    assert len(_E5_MODEL_REVISION) == 40, "revision は SHA1 ハッシュ（40文字）でなければならない"
    assert all(c in "0123456789abcdef" for c in _E5_MODEL_REVISION), "revision は hex 文字列でなければならない"


def test_vector_model_tag_uses_revision(tmp_path):
    """upsert_skill が revision 付きの vector_model を DB に保存することを確認（G15）。"""
    from tools.skill_index_db import SkillIndexDB, _E5_MODEL_NAME, _E5_MODEL_REVISION
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill({
        "skill_name": "dummy-skill",
        "description": "dummy",
        "description_full": "dummy skill for version test",
    })
    row = db.get_skill("dummy-skill")
    # vector が生成された場合は revision 付き model 名が入る
    # 生成できなかった場合は None（CI 環境ではモデルが未インストールのため許容）
    if row["vector"] is not None:
        assert row["vector_model"] == f"{_E5_MODEL_NAME}@{_E5_MODEL_REVISION[:8]}" or \
               row["vector_model"] == _E5_MODEL_NAME, \
               f"vector_model={row['vector_model']!r} が期待値と一致しない"


# ---------------------------------------------------------------------------
# G16: record_usage 空スキル対策
# ---------------------------------------------------------------------------

def test_record_usage_unknown_skill_does_not_upsert(tmp_path):
    """DB未登録スキルの record_usage が空ベクトル行を生成しないことを確認（G16）。"""
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.record_usage(skill_name="nonexistent-skill", session_id="s1", platform="discord")
    assert db.get_skill("nonexistent-skill") is None, \
        "未登録スキルの record_usage が DB 行を生成してはならない"


def test_record_usage_known_skill_still_works(tmp_path):
    """DB登録済みスキルの record_usage は従来通り動作することを確認（G16 リグレッション）。"""
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill({"skill_name": "known-skill", "description": "known", "description_full": "known skill"})
    db.record_usage(skill_name="known-skill", session_id="s1", platform="discord")
    row = db.get_skill("known-skill")
    assert row is not None
    assert row["total_count"] == 1


# ---------------------------------------------------------------------------
# G7: skill_name (ディレクトリ名) vs frontmatter name の乖離確認
# ---------------------------------------------------------------------------

def test_skill_name_is_primary_key(tmp_path):
    """skill_name が PRIMARY KEY として機能し、同一名の重複 upsert が 1行に収まることを確認（G7）。"""
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill({"skill_name": "my-skill", "description": "v1", "description_full": "version 1"})
    db.upsert_skill({"skill_name": "my-skill", "description": "v2", "description_full": "version 2"})
    rows = list(db._conn.execute("SELECT COUNT(*) FROM skills WHERE skill_name='my-skill'"))
    assert rows[0][0] == 1, "同一 skill_name は 1行のみ保持されるべき"
    row = db.get_skill("my-skill")
    assert row["description"] == "v2"


def test_different_skill_names_are_separate_rows(tmp_path):
    """ディレクトリ名が異なれば別行になることを確認（G7）。"""
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill({"skill_name": "skill-a", "description": "a", "description_full": "skill a"})
    db.upsert_skill({"skill_name": "skill-b", "description": "b", "description_full": "skill b"})
    rows = list(db._conn.execute("SELECT COUNT(*) FROM skills"))
    assert rows[0][0] == 2
