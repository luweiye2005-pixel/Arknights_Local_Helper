"""遗物效果解析与合并。"""
from unittest.mock import patch

from app.combat.relics import (
    CombatModifiers,
    EnemyStatModifiers,
    build_relic_modifiers,
    modifiers_from_effect_rows,
    modifiers_from_patch,
    parse_relic_text,
)


def test_parse_aspd_and_true_damage():
    m = parse_relic_text("刃", "攻击速度+30，造成真实伤害")
    assert abs(m.aspd - 30) < 1e-6
    assert m.true_damage is True


def test_parse_ignore_def_and_phys():
    m = parse_relic_text("枪", "无视防御力20%，物理伤害+15%")
    assert abs(m.ignore_def_pct - 0.2) < 1e-6
    assert abs(m.phys_damage_pct - 0.15) < 1e-6


def test_modifiers_from_patch():
    m = modifiers_from_patch({"atk_pct": 0.25, "aspd": 10, "true_damage": True, "note": "x"})
    assert abs(m.atk_pct - 0.25) < 1e-6
    assert m.true_damage is True
    assert m.notes


def test_modifiers_from_effect_rows():
    rows = [
        {"target": "operator", "attr": "atk_pct", "value": 0.1},
        {"target": "operator", "attr": "aspd", "value": 12},
        {"target": "enemy", "attr": "atk_pct", "value": 0.5},  # 忽略
        {"target": "operator", "attr": "true_damage", "value": 1},
    ]
    m = modifiers_from_effect_rows(rows)
    assert abs(m.atk_pct - 0.1) < 1e-6
    assert abs(m.aspd - 12) < 1e-6
    assert m.true_damage is True


def test_merge_caps_ignore_def():
    a = CombatModifiers(ignore_def_pct=0.7)
    b = CombatModifiers(ignore_def_pct=0.5)
    assert abs(a.merge(b).ignore_def_pct - 1.0) < 1e-6


def test_build_prefers_mysql_effects_when_present():
    relics = [{"id": "r1", "name": "假", "usage": "攻击力+99%"}]
    fake_rows = [{"relic_id": "r1", "target": "operator", "attr": "atk_pct", "value": 0.05, "note": "db"}]
    with patch("app.data.db.get_relic_effects_merged", return_value=fake_rows):
        m = build_relic_modifiers(relics)
    assert abs(m.atk_pct - 0.05) < 1e-6  # 用 DB 而非 99%


def test_build_fallback_text_when_mysql_empty():
    relics = [{"id": "not_in_db_xxx", "name": "A", "usage": "攻击力+10%"}]
    with (
        patch("app.data.db.get_relic_effects_merged", return_value=[]),
        patch("app.data.db.resolve_relic_for_grade", return_value=None),
        patch("app.data.db.get_relic_row", return_value=None),
    ):
        m = build_relic_modifiers(relics)
    assert abs(m.atk_pct - 0.1) < 1e-6


def test_build_with_relic_ids_falls_back_to_db_text():
    with (
        patch("app.data.db.get_relic_effects_merged", return_value=[]),
        patch(
            "app.data.db.resolve_relic_for_grade",
            return_value={"id": "x", "name": "开裂", "usage": "所有敌方单位的攻击力-7%"},
        ),
        patch("app.data.db.get_relic_row", return_value=None),
    ):
        # 敌方减益不影响干员面板
        m = build_relic_modifiers(relic_ids=["x"])
    assert m.atk_pct == 0.0
    assert any("无面板数值效果" in n for n in m.notes)


def test_parse_enemy_fang_and_compound():
    from app.combat.relics import parse_enemy_relic_text

    m = parse_enemy_relic_text("", "所有敌方单位的攻击力-7%")
    assert abs(m.atk_pct - (-0.07)) < 1e-6
    m2 = parse_enemy_relic_text("", "所有敌方单位的攻击力、防御力、生命+40%")
    assert abs(m2.atk_pct - 0.4) < 1e-6
    assert abs(m2.def_pct - 0.4) < 1e-6
    assert abs(m2.hp_pct - 0.4) < 1e-6


# ---------- EnemyStatModifiers ----------

def test_enemy_stat_modifiers_defaults():
    m = EnemyStatModifiers()
    assert m.hp_pct == 0.0
    assert m.atk_pct == 0.0
    assert m.def_pct == 0.0
    assert m.aspd == 0.0
    assert m.res_flat == 0.0
    assert m.notes == []


def test_enemy_stat_modifiers_merge():
    a = EnemyStatModifiers(
        hp_pct=0.1,
        atk_pct=0.2,
        def_pct=0.15,
        aspd=5,
        res_flat=10,
        notes=["a"],
    )
    b = EnemyStatModifiers(
        hp_pct=0.1,
        atk_pct=-0.05,
        def_pct=0.0,
        aspd=-3,
        res_flat=-5,
        notes=["b"],
    )
    m = a.merge(b)
    assert abs(m.hp_pct - 0.2) < 1e-6
    assert abs(m.atk_pct - 0.15) < 1e-6
    assert abs(m.def_pct - 0.15) < 1e-6
    assert m.aspd == 2
    assert m.res_flat == 5
    assert m.notes == ["a", "b"]


def test_enemy_stat_modifiers_to_dict():
    m = EnemyStatModifiers(
        hp_pct=0.2,
        atk_pct=0.15,
        notes=["测试"],
    )
    d = m.to_dict()
    assert d["hp_pct"] == 0.2
    assert d["atk_pct"] == 0.15
    assert d["def_pct"] == 0.0
    assert d["notes"] == ["测试"]


def test_enemy_stat_modifiers_merge_zero():
    """零值合并后应保持不变。"""
    a = EnemyStatModifiers(hp_pct=0.3, atk_pct=0.0)
    b = EnemyStatModifiers()
    m = a.merge(b)
    assert abs(m.hp_pct - 0.3) < 1e-6
    assert m.atk_pct == 0.0
