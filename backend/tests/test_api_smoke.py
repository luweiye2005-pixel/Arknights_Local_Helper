"""FastAPI 冒烟测试（mock 数据库）。"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_docs():
    r = client.get("/docs")
    assert r.status_code == 200


def test_list_operators_mysql_source():
    fake = [{"id": "char_1", "name": "阿米娅", "rarity": 5, "profession": "CASTER", "profession_cn": "术师"}]
    with patch("app.api.operators.gdb.search_operators", return_value=fake):
        r = client.get("/api/v1/operators", params={"q": "阿", "limit": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "mysql"
    assert body["items"][0]["name"] == "阿米娅"


def test_operator_skills_mysql_source():
    fake_skills = [
        {
            "skill_id": "skchr_ulpia_3",
            "skill_name": "必须开辟的通路",
            "max_level": 10,
            "levels": [{"level": 10, "atk_pct": 2.6, "atk_scale": 1.6}],
        }
    ]
    with (
        patch("app.api.operators.gdb.get_operator_detail", return_value={"id": "char_4145_ulpia"}),
        patch("app.api.operators.gdb.get_operator_skills", return_value=fake_skills),
    ):
        response = client.get("/api/v1/operators/char_4145_ulpia/skills")
    assert response.status_code == 200
    assert response.json()["source"] == "mysql"
    assert response.json()["skills"][0]["levels"][0]["atk_pct"] == 2.6


def test_theme_difficulties_unique_keys():
    fake = [
        {
            "id": 1,
            "key": "NORMAL:0",
            "theme_id": "rogue_1",
            "mode_difficulty": "NORMAL",
            "grade": 0,
            "equivalent_grade": 0,
            "name": "常规",
        },
        {
            "id": 2,
            "key": "EASY:0",
            "theme_id": "rogue_1",
            "mode_difficulty": "EASY",
            "grade": 0,
            "equivalent_grade": 0,
            "name": "简单",
        },
    ]
    with patch("app.api.relics.gdb.list_theme_difficulties", return_value=fake):
        r = client.get("/api/v1/relics/themes/rogue_1/difficulties")
    assert r.status_code == 200
    keys = [x["key"] for x in r.json()["items"]]
    assert len(keys) == len(set(keys))


def test_panel_calc_endpoint():
    fake_result = {
        "operator": {"id": "char_1", "name": "测"},
        "final_panel": {"atk": 1},
        "steps": [],
        "disclaimer": "x",
        "base_panel": {},
        "bonus": {},
        "modifiers": {},
        "relics_applied": [],
        "config": {},
        "module": None,
    }
    with patch("app.api.calc.calculate_panel", return_value=fake_result):
        r = client.post(
            "/api/v1/calc/panel",
            json={"operator_id": "char_1", "elite": 2, "level": 80, "equivalent_grade": 0},
        )
    assert r.status_code == 200
    assert r.json()["final_panel"]["atk"] == 1


def test_relic_icon_fallback_svg_when_missing(monkeypatch):
    monkeypatch.setattr("app.api.assets.la.resolve_local_icon", lambda _rid: None)
    r = client.get("/api/v1/assets/relic/not_exist_relic")
    assert r.status_code == 200
    assert "svg" in r.headers.get("content-type", "")
