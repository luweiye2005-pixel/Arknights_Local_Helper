"""战斗公式单元测试。"""
from app.combat.engine import (
    arts_damage,
    attack_interval,
    calc_hit_damage,
    physical_damage,
    product_atk_scales,
    resolve_hit_from_panels,
)
from app.combat.relics import parse_relic_text, build_relic_modifiers


def test_physical_damage_zero_def():
    assert abs(physical_damage(100, 0) - 100) < 1e-6


def test_physical_damage_subtraction():
    # ATK 500 vs DEF 200 → 300；高于 5% 保底
    assert abs(physical_damage(500, 200) - 300) < 1e-6
    # 抛光：ATK 100 vs DEF 1000 → 5
    assert abs(physical_damage(100, 1000) - 5) < 1e-6


def test_physical_ignore_def():
    # DEF 200，无视 50% → 有效防 100；500-100=400
    assert abs(physical_damage(500, 200, ignore_def_pct=0.5) - 400) < 1e-6


def test_arts_damage_50_res():
    assert abs(arts_damage(100, 50) - 50) < 1e-6


def test_attack_interval():
    assert abs(attack_interval(1.0, 100) - 1.0) < 1e-6
    assert abs(attack_interval(1.0, 200) - 0.5) < 1e-6


def test_true_damage():
    d = calc_hit_damage(200, "TRUE", enemy_def=9999, enemy_res=90, scale=2.0)
    assert abs(d["final"] - 400) < 1e-6


def test_elemental_damage_and_taken_amplification():
    d = calc_hit_damage(
        200,
        "ELEMENTAL",
        enemy_def=9999,
        enemy_res=100,
        scale=1.5,
        elemental_damage_taken_pct=1.0,
    )
    assert abs(d["basic"] - 300) < 1e-6
    assert abs(d["final"] - 600) < 1e-6


def test_product_scales_wishadel():
    # 125% × 220% × 造成100% = 2.75
    assert abs(product_atk_scales([125, 220], 100) - 2.75) < 1e-9


def test_wishadel_like_hit():
    # 基础面板 500，技能+180% → 战斗 ATK 1400
    # ×1.25×2.2 = 3850 结算；对 200 防 → 3650；×1.35×0.8
    combat = 500 * (1 + 1.8)
    info = resolve_hit_from_panels(
        combat,
        damage_type="PHYS",
        enemy_def=200,
        skill_manual={"atk_scale_to": [125, 220], "damage_scale_pct": 100},
        enemy_manual={"phys_damage_taken_pct": 0.35, "phys_damage_reduction": 0.2},
    )
    hit_atk = 1400 * 1.25 * 2.2
    basic = hit_atk - 200
    expected = basic * 1.35 * 0.8
    assert abs(info["hit_atk"] - hit_atk) < 1e-6
    assert abs(info["hit_damage"] - expected) < 1e-6


def test_user_scenario_panel_then_hit():
    # 500 +50模组 → 550；藏品+50% → 825；提升至150%×造成125%；DEF200；加深35%；免伤20%
    combat = (500 + 50) * 1.5
    info = resolve_hit_from_panels(
        combat,
        damage_type="PHYS",
        enemy_def=200,
        skill_manual={"atk_scale_to": [150], "damage_scale_pct": 125},
        enemy_manual={"phys_damage_taken_pct": 0.35, "phys_damage_reduction": 0.2},
    )
    raw = 825 * 1.5 * 1.25
    basic = raw - 200
    expected = basic * 1.35 * 0.8
    assert abs(info["hit_damage"] - expected) < 1e-6
    assert abs(expected - 1454.625) < 1e-6


def test_phys_damage_amp_not_double_counted():
    from app.combat.relics import parse_relic_text, normalize_damage_amps

    m = parse_relic_text("复仇者", "所有敌人受到的物理伤害+35%")
    assert abs(m.phys_damage_pct - 0.35) < 1e-9
    assert abs(m.damage_pct) < 1e-9

    # 旧双计数据归一
    bad = __import__("app.combat.relics", fromlist=["CombatModifiers"]).CombatModifiers(
        damage_pct=0.35, phys_damage_pct=0.35
    )
    normalize_damage_amps(bad)
    assert abs(bad.phys_damage_pct - 0.35) < 1e-9
    assert abs(bad.damage_pct) < 1e-9



def test_build_modifiers_merge():
    from unittest.mock import patch
    from app.combat.relics import CombatModifiers

    relics = [
        {"id": "a", "name": "A", "usage": "攻击力+10%"},
        {"id": "b", "name": "B", "usage": "造成的伤害+15%"},
    ]
    with (
        patch("app.data.db.resolve_relic_for_grade", return_value=None),
        patch("app.data.db.get_relic_row", side_effect=lambda rid: next(r for r in relics if r["id"] == rid)),
        patch("app.data.db.get_relic_effects_merged", side_effect=[
            [{"target": "operator", "attr": "atk_pct", "value": 0.1}],
            [{"target": "operator", "attr": "damage_pct", "value": 0.15}],
        ]),
    ):
        m = build_relic_modifiers(relics=relics, relic_ids=["a", "b"])
    assert abs(m.atk_pct - 0.1) < 1e-6
    assert abs(m.damage_pct - 0.15) < 1e-6
