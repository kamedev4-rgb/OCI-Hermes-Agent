import json
import sqlite3

from tools.skill_index_db import SkillIndexDB
from tools.skill_inventory_tool import skill_inventory


def test_search_can_include_disabled_skills(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill(
        {
            "skill_name": "alpha-skill",
            "category": "devops",
            "description": "Alpha description",
            "source": "builtin",
        }
    )
    db.upsert_skill(
        {
            "skill_name": "beta-skill",
            "category": "devops",
            "description": "Beta description",
            "source": "builtin",
        }
    )
    db.set_enabled("beta-skill", False)

    result = json.loads(
        skill_inventory(
            action="search",
            query="skill",
            include_disabled=True,
            limit=10,
        )
    )

    names = {item["skill_name"] for item in result["skills"]}
    assert names == {"alpha-skill", "beta-skill"}
    beta = next(item for item in result["skills"] if item["skill_name"] == "beta-skill")
    assert beta["enabled"] is False


def test_toggle_updates_config_and_db(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    db = SkillIndexDB(tmp_path / "skill_index.db")
    db.upsert_skill(
        {
            "skill_name": "alpha-skill",
            "category": "devops",
            "description": "Alpha description",
            "source": "builtin",
        }
    )

    disabled = json.loads(skill_inventory(action="toggle", skill_name="alpha-skill", enabled=False))
    assert disabled["success"] is True
    config_text = (tmp_path / "config.yaml").read_text()
    assert "alpha-skill" in config_text
    assert SkillIndexDB(tmp_path / "skill_index.db").get_skill("alpha-skill")["enabled"] == 0

    enabled = json.loads(skill_inventory(action="toggle", skill_name="alpha-skill", enabled=True))
    assert enabled["success"] is True
    config_text = (tmp_path / "config.yaml").read_text()
    assert "alpha-skill" not in config_text
    assert SkillIndexDB(tmp_path / "skill_index.db").get_skill("alpha-skill")["enabled"] == 1
