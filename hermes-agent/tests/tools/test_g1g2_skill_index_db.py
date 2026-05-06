"""
G1/G2 テスト: count_skills() と has_all_skills() の動作確認。
"""

from tools.skill_index_db import SkillIndexDB, _E5_MODEL_NAME


def _entry(name, desc="desc", desc_full=None):
    return {
        "skill_name": name,
        "description": desc,
        "description_full": desc_full or desc,
    }


def _upsert_with_vector(db, name, desc="desc", desc_full=None):
    """vectorを持たない行をupsertする（ベクトル化はスキップ）。"""
    db.upsert_skill({
        "skill_name": name,
        "description": desc,
        "description_full": desc_full or desc,
    })


# ---------------------------------------------------------------------------
# count_skills テスト
# ---------------------------------------------------------------------------

def test_count_skills_empty_db_returns_zero(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")
    assert db.count_skills() == 0


def test_count_skills_returns_correct_count(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")
    _upsert_with_vector(db, "skill-a")
    _upsert_with_vector(db, "skill-b")
    assert db.count_skills() == 2


# ---------------------------------------------------------------------------
# has_all_skills テスト
# ---------------------------------------------------------------------------

def test_has_all_skills_empty_entries_returns_false(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")
    assert db.has_all_skills([]) is False


def test_has_all_skills_returns_false_when_db_empty(tmp_path):
    db = SkillIndexDB(tmp_path / "skill_index.db")
    assert db.has_all_skills([_entry("skill-a")]) is False


def test_has_all_skills_returns_false_when_vector_null(tmp_path):
    """vector_model=NULL の行は False を返す（F4: count_skills誤判定対処）。"""
    db = SkillIndexDB(tmp_path / "skill_index.db")
    # upsertしてから vector_model を NULL に戻す（NOT NULL制約を回避）
    _upsert_with_vector(db, "skill-a", desc="desc")
    db._conn.execute("UPDATE skills SET vector_model=NULL WHERE skill_name=?", ("skill-a",))
    db._conn.commit()
    assert db.has_all_skills([_entry("skill-a")]) is False


def test_has_all_skills_returns_false_when_one_missing(tmp_path):
    """一件でも欠けるとFalse。"""
    db = SkillIndexDB(tmp_path / "skill_index.db")
    _upsert_with_vector(db, "skill-a")
    # skill-bは登録しない
    entries = [_entry("skill-a"), _entry("skill-b")]
    assert db.has_all_skills(entries) is False


def test_has_all_skills_returns_false_when_description_changed(tmp_path):
    """description_full が変化した場合はFalse（F2: rsync変更検知）。"""
    db = SkillIndexDB(tmp_path / "skill_index.db")
    _upsert_with_vector(db, "skill-a", desc_full="original description")
    # vector_modelが設定されている場合のみF2テストが意味を持つ
    # upsertの後にvector_modelを直接更新して確認
    db._conn.execute(
        f"UPDATE skills SET vector_model=? WHERE skill_name=?",
        (_E5_MODEL_NAME, "skill-a")
    )
    db._conn.commit()
    # description_full が変わったentryを渡す
    entries = [_entry("skill-a", desc_full="changed description")]
    assert db.has_all_skills(entries) is False


def test_has_all_skills_returns_true_when_all_match(tmp_path):
    """全件存在 + vector_model設定済み + description一致 → True。"""
    db = SkillIndexDB(tmp_path / "skill_index.db")
    _upsert_with_vector(db, "skill-a", desc_full="same description")
    # vector_modelを手動で設定
    db._conn.execute(
        f"UPDATE skills SET vector_model=? WHERE skill_name=?",
        (_E5_MODEL_NAME, "skill-a")
    )
    db._conn.commit()
    entries = [_entry("skill-a", desc_full="same description")]
    assert db.has_all_skills(entries) is True
