"""逻辑回归：难度解析、技能倍率拆分、潜能/天赋、藏品启发式。"""
from app.combat.attributes import (
    potential_flat_bonus,
    skill_multiplier_and_duration,
    talent_panel_bonus,
)
from app.combat.relics import parse_enemy_relic_text, parse_relic_text
from app.data.mysql_db import _parse_rule_desc_mods, _skill_level_row


def test_parse_rule_desc_damage_taken_all():
    mods = _parse_rule_desc_mods("rogue_x", 10, "所有敌人受到的物理与法术伤害降低10%")
    attrs = {(m["target"], m["attr"], m["value"]) for m in mods}
    assert ("enemy", "damage_taken_phys_pct", -0.1) in attrs
    assert ("enemy", "damage_taken_arts_pct", -0.1) in attrs


def test_parse_rule_desc_elite_hp_not_all_enemies():
    mods = _parse_rule_desc_mods("rogue_4", 4, "精英及领袖敌人的生命值+20%")
    assert all(m["target"] in ("elite_enemy", "boss") for m in mods)
    assert any(m["attr"] == "hp_pct" and abs(m["value"] - 0.2) < 1e-6 for m in mods)
    assert not any(m["target"] == "enemy" for m in mods)


def test_parse_rule_desc_elite_damage_taken():
    mods = _parse_rule_desc_mods(
        "rogue_4", 10, "可同时部署人数-1，精英及领袖敌人受到的物理与法术伤害降低10%"
    )
    assert any(m["target"] == "elite_enemy" and m["attr"] == "damage_taken_phys_pct" for m in mods)
    assert any(m["target"] == "elite_enemy" and m["attr"] == "damage_taken_arts_pct" for m in mods)
    assert any(m["target"] == "boss" and m["attr"] == "damage_taken_arts_pct" for m in mods)
    # 不应误写到全体 enemy
    assert not any(m["target"] == "enemy" and "damage_taken" in m["attr"] for m in mods)


def test_parse_rule_desc_conditional_skipped():
    mods = _parse_rule_desc_mods(
        "rogue_4",
        14,
        "处于年代印痕中的敌人受到的物理与法术伤害降低50%，特雷西斯，黑冠尊主的最大生命值提升",
    )
    assert not any("damage_taken" in m["attr"] for m in mods)


def test_parse_rule_desc_enemy_atk():
    mods = _parse_rule_desc_mods("rogue_x", 5, "敌人攻击力提升15%")
    assert any(m["attr"] == "atk_pct" and abs(m["value"] - 0.15) < 1e-6 and m["target"] == "enemy" for m in mods)


def test_parse_rule_desc_empty():
    assert _parse_rule_desc_mods("rogue_x", 0, "") == []


def test_skill_splits_atk_and_atk_scale():
    levels = [
        {
            "name": "无言为真",
            "duration": 20,
            "blackboard": [
                {"key": "atk", "value": 2.75},
                {"key": "atk_scale", "value": 1.85},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_pct"] - 2.75) < 1e-6
    assert abs(info["atk_scale"] - 1.85) < 1e-6


def test_skill_level_row_preserves_raw_and_parsed_data():
    row = _skill_level_row(
        "char_4145_ulpia",
        "skchr_ulpia_3",
        9,
        {
            "name": "必须开辟的通路",
            "duration": 25,
            "description": "生命+{max_hp:0%}，攻击+{atk:0%}，造成{atk_scale:0%}伤害",
            "sp_data": {"spCost": 25, "initSp": 20},
            "blackboard": [
                {"key": "max_hp", "value": 0.8},
                {"key": "atk", "value": 2.6},
                {"key": "atk_scale", "value": 1.6},
            ],
        },
    )
    import json

    parsed = json.loads(row["parsed_effects"])
    assert row["level"] == 10
    assert row["sp_cost"] == 25
    assert row["sp_init"] == 20
    assert json.loads(row["blackboard"])[1]["value"] == 2.6
    assert parsed["atk_pct"] == 2.6
    assert parsed["hp_pct"] == 0.8
    assert parsed["atk_scale"] == 1.6


def test_potential_flat_bonus_normalized():
    ranks = [
        {"hp": 200, "atk": 0, "def": 0, "aspd": 0, "res": 0},
        {"hp": 0, "atk": 30, "def": 0, "aspd": 0, "res": 0},
    ]
    b0 = potential_flat_bonus(ranks, 0)
    assert b0["hp"] == 0 and b0["atk"] == 0
    b1 = potential_flat_bonus(ranks, 1)
    assert b1["hp"] == 200 and b1["atk"] == 0
    b2 = potential_flat_bonus(ranks, 2)
    assert b2["hp"] == 200 and b2["atk"] == 30


def test_talent_picks_highest_eligible():
    talents = [
        {"index": 0, "unlock_elite": 1, "potential_rank": 0, "blackboard": [{"key": "atk", "value": 0.05}]},
        {"index": 0, "unlock_elite": 2, "potential_rank": 0, "blackboard": [{"key": "atk", "value": 0.10}]},
        {"index": 0, "unlock_elite": 2, "potential_rank": 4, "blackboard": [{"key": "atk", "value": 0.12}]},
    ]
    b = talent_panel_bonus(talents, elite=2, potential=5)
    assert abs(b["atk_pct"] - 0.12) < 1e-6
    b2 = talent_panel_bonus(talents, elite=1, potential=0)
    assert abs(b2["atk_pct"] - 0.05) < 1e-6


def test_relic_parse_skips_situational_true_damage_receive():
    mod = parse_relic_text("测试", "受到真实伤害提升")
    assert mod.true_damage is False


def test_relic_parse_ally_atk():
    mod = parse_relic_text("测试", "所有干员的攻击力提升20%")
    assert abs(mod.atk_pct - 0.2) < 1e-6


def test_enemy_relic_parse_basic():
    mod = parse_enemy_relic_text("测试", "所有敌人的生命值+30%")
    assert abs(mod.hp_pct - 0.3) < 1e-6


def test_skill_res_flat_and_pct():
    flat_levels = [
        {
            "name": "提喻",
            "duration": 20,
            "description": "法术抗性<@ba.vup>+{magic_resistance}</>",
            "blackboard": [{"key": "magic_resistance", "value": 50.0}],
        }
    ]
    info = skill_multiplier_and_duration(flat_levels, 1)
    assert abs(info["res_flat"] - 50.0) < 1e-6
    assert abs(info.get("res_pct") or 0) < 1e-9

    pct_levels = [
        {
            "name": "圣域",
            "duration": 20,
            "description": "法术抗性<@ba.vup>+{magic_resistance:0%}</>",
            "blackboard": [{"key": "magic_resistance", "value": 0.8}],
        }
    ]
    info = skill_multiplier_and_duration(pct_levels, 1)
    assert abs(info["res_pct"] - 0.8) < 1e-6
    assert abs(info["res_flat"]) < 1e-9

    debuff_levels = [
        {
            "name": "火焰剥离",
            "duration": 5,
            "description": "法术抗性<@ba.vup>-{-magic_resistance:0%}</>",
            "blackboard": [{"key": "magic_resistance", "value": -0.2}],
        }
    ]
    info = skill_multiplier_and_duration(debuff_levels, 1)
    assert abs(info["res_flat"]) < 1e-9
    assert abs(info.get("res_pct") or 0) < 1e-9
    assert abs(info["enemy_effects"]["res_pct"] - (-0.2)) < 1e-6


def test_skill_self_def_down_silverash_style():
    """银灰真银斩：自身防御下降，不进敌人。"""
    levels = [
        {
            "name": "真银斩",
            "duration": 20,
            "description": "防御力<@ba.vdown>-{-def:0%}</>，攻击力<@ba.vup>+{atk:0%}</>",
            "blackboard": [
                {"key": "def", "value": -0.7},
                {"key": "atk", "value": 2.0},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["def_pct"] - (-0.7)) < 1e-6
    assert abs(info["atk_pct"] - 2.0) < 1e-6
    ee = info["enemy_effects"]
    assert abs(ee["def_pct"]) < 1e-9
    assert abs(ee["atk_pct"]) < 1e-9


def test_skill_enemy_debuff_pramanix_style():
    """初雪自然震慑：敌人防御/法抗下降，不进干员。"""
    levels = [
        {
            "name": "自然震慑",
            "duration": 20,
            "description": (
                "攻击范围内所有敌人防御力<@ba.vup>-{-def:0%}</>，"
                "法术抗性<@ba.vup>-{-magic_resistance:0%}</>"
            ),
            "blackboard": [
                {"key": "def", "value": -0.6},
                {"key": "magic_resistance", "value": -0.3},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["def_pct"]) < 1e-9
    assert abs(info.get("res_pct") or 0) < 1e-9
    ee = info["enemy_effects"]
    assert abs(ee["def_pct"] - (-0.6)) < 1e-6
    assert abs(ee["res_pct"] - (-0.3)) < 1e-6
