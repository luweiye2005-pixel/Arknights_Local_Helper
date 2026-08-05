"""条件藏品、局外/手填加成。"""
from unittest.mock import patch

from app.combat.panel import calculate_panel
from app.combat.relics import (
    build_conditional_relic_modifiers,
    manual_bonus_to_modifiers,
    outer_buff_to_modifiers,
    safe_eval_expr,
)


def test_safe_eval_floor_expr():
    assert abs(safe_eval_expr("floor(gold/5)*7", {"gold": 23}) - 28) < 1e-6
    assert abs(safe_eval_expr("floor(gold/5)*7", {"gold": 25}) - 35) < 1e-6


def test_safe_eval_rejects_bad_nodes():
    try:
        safe_eval_expr("__import__('os').system('x')", {})
        assert False
    except Exception:
        pass


def test_conditional_gold_cup_and_toggle():
    with patch(
        "app.combat.relic_conditions.load_relic_conditions",
        return_value={
            "r_gold": {
                "name": "金",
                "params": [{"id": "gold", "type": "number", "default": 0}],
                "operator_effects": [{"attr": "aspd", "expr": "floor(gold/5)*7"}],
            },
            "r_anger": {
                "name": "怒",
                "params": [{"id": "active", "type": "toggle", "default": False}],
                "operator_effects": [{"attr": "atk_pct", "value": 1.0, "when": "active"}],
            },
        },
    ):
        on = build_conditional_relic_modifiers(
            ["r_gold", "r_anger"],
            {"r_gold": {"gold": 25}, "r_anger": {"active": True}},
        )
        off = build_conditional_relic_modifiers(["r_anger"], {"r_anger": {"active": False}})
    assert abs(on.aspd - 35) < 1e-6
    assert abs(on.atk_pct - 1.0) < 1e-6
    assert off.atk_pct == 0.0


def test_outer_and_manual_modifiers():
    outer = outer_buff_to_modifiers({"name": "x", "atk_pct": 0.1, "hp_pct": 0.05})
    manual = manual_bonus_to_modifiers({"atk_pct": 0.2, "aspd": 15})
    assert abs(outer.atk_pct - 0.1) < 1e-6
    assert abs(manual.atk_pct - 0.2) < 1e-6
    assert abs(manual.aspd - 15) < 1e-6


def test_condition_patch_loaded_and_no_double_count():
    from app.combat.relics import build_relic_modifiers, load_relic_conditions

    schemas = load_relic_conditions()
    assert "rogue_1_relic_q28" in schemas
    assert "rogue_1_relic_q31" in schemas
    assert len(schemas) >= 200

    with (
        patch("app.data.db.get_relic_row", return_value={
            "id": "rogue_1_relic_q31",
            "name": "叙拉古人的愤怒",
            "usage": "所有干员技能触发后1秒内攻击力+100%",
        }),
        patch("app.data.db.resolve_relic_for_grade", return_value=None),
        patch(
            "app.data.db.get_relic_effects_merged",
            return_value=[{"target": "operator", "attr": "atk_pct", "value": 1.0}],
        ),
    ):
        base = build_relic_modifiers(relic_ids=["rogue_1_relic_q31"])
        cond = build_conditional_relic_modifiers(
            ["rogue_1_relic_q31"], {"rogue_1_relic_q31": {"active": True}}
        )
    # 常驻面板应被剥离，条件开启后才有 +100%
    assert abs(base.atk_pct) < 1e-9
    assert abs(cond.atk_pct - 1.0) < 1e-6


def _fake_operator():
    return {
        "id": "char_test",
        "name": "测试干员",
        "profession_cn": "近卫",
        "rarity": 6,
        "modules": [],
        "raw_phases": [
            {"attributesKeyFrames": []},
            {"attributesKeyFrames": []},
            {
                "attributesKeyFrames": [
                    {
                        "level": 1,
                        "data": {
                            "atk": 100,
                            "maxHp": 1000,
                            "def": 100,
                            "magicResistance": 0,
                            "attackSpeed": 100,
                            "baseAttackTime": 1.0,
                        },
                    },
                    {
                        "level": 90,
                        "data": {
                            "atk": 100,
                            "maxHp": 1000,
                            "def": 100,
                            "magicResistance": 0,
                            "attackSpeed": 100,
                            "baseAttackTime": 1.0,
                        },
                    },
                ]
            },
        ],
        "favor_key_frames": [
            {"level": 0, "data": {"atk": 0, "maxHp": 0, "def": 0}},
            {"level": 50, "data": {"atk": 0, "maxHp": 0, "def": 0}},
        ],
    }


def test_panel_outer_off_and_manual():
    op = _fake_operator()
    with (
        patch("app.combat.panel.gdb.get_operator_detail", return_value=op),
        patch("app.combat.panel.gdb.resolve_relic_for_grade", return_value=None),
        patch("app.combat.panel.gdb.get_relic_row", return_value=None),
        patch("app.combat.panel.build_relic_modifiers", return_value=__import__(
            "app.combat.relics", fromlist=["CombatModifiers"]
        ).CombatModifiers()),
        patch("app.combat.panel.build_conditional_relic_modifiers", return_value=__import__(
            "app.combat.relics", fromlist=["CombatModifiers"]
        ).CombatModifiers()),
        patch(
            "app.combat.panel.get_outer_buff",
            return_value={"name": "满", "atk_pct": 0.5, "hp_pct": 0, "def_pct": 0, "aspd": 0},
        ),
    ):
        on = calculate_panel(
            {
                "operator_id": "char_test",
                "elite": 2,
                "level": 90,
                "theme_id": "rogue_1",
                "apply_outer_buff": True,
                "manual_bonus": {"atk_pct": 0.1},
            }
        )
        off = calculate_panel(
            {
                "operator_id": "char_test",
                "elite": 2,
                "level": 90,
                "theme_id": "rogue_1",
                "apply_outer_buff": False,
                "manual_bonus": {"atk_pct": 0.1},
            }
        )
    # base 100; on: *1.6 = 160; off: *1.1 = 110
    assert abs(on["final_panel"]["atk"] - 160) < 1e-6
    assert abs(off["final_panel"]["atk"] - 110) < 1e-6
    assert on["bonus"]["apply_outer_buff"] is True
    assert off["bonus"]["apply_outer_buff"] is False


def test_auto_applies_profession_and_position():
    from app.combat.relics import match_applies_auto

    assert match_applies_auto(
        {"profession": ["近卫", "WARRIOR"]},
        {"profession": "WARRIOR", "profession_cn": "近卫"},
    )
    assert not match_applies_auto(
        {"profession": ["近卫", "WARRIOR"]},
        {"profession": "SNIPER", "profession_cn": "狙击"},
    )
    assert match_applies_auto({"position": "MELEE"}, {"position": "MELEE"})
    assert not match_applies_auto({"position": "MELEE"}, {"position": "RANGED"})


def test_auto_rule_can_drive_multiple_named_condition_params():
    schema = {
        "params": [
            {"id": "primary_applies", "type": "toggle", "default": False, "auto": {"profession": ["SPECIAL"]}},
            {"id": "secondary_applies", "type": "toggle", "default": False, "auto": {"profession": ["CASTER"]}},
        ],
        "operator_effects": [
            {"attr": "atk_pct", "value": 0.30, "when": "primary_applies"},
            {"attr": "atk_pct", "value": 0.03, "when": "secondary_applies"},
        ],
    }
    special = {"profession": "SPECIAL", "profession_cn": "特种"}
    caster = {"profession": "CASTER", "profession_cn": "术师"}
    with patch("app.combat.relic_conditions.load_relic_conditions", return_value={"dual": schema}):
        assert abs(build_conditional_relic_modifiers(["dual"], {}, special).atk_pct - 0.30) < 1e-9
        assert abs(build_conditional_relic_modifiers(["dual"], {}, caster).atk_pct - 0.03) < 1e-9


def test_po_fu_chen_zhou_debuff_and_auto():
    from app.combat.relics import load_relic_conditions

    schemas = load_relic_conditions()
    schema = schemas["rogue_1_relic_p10"]
    attrs = {e["attr"]: e["value"] for e in schema["operator_effects"]}
    assert abs(attrs["atk_pct"] - 0.4) < 1e-9
    assert abs(attrs["def_pct"] + 0.4) < 1e-9
    assert abs(attrs["aspd"] - 30) < 1e-9

    guard = {"profession": "WARRIOR", "profession_cn": "近卫", "position": "MELEE"}
    sniper = {"profession": "SNIPER", "profession_cn": "狙击", "position": "RANGED"}
    on = build_conditional_relic_modifiers(["rogue_1_relic_p10"], {}, operator=guard)
    off = build_conditional_relic_modifiers(["rogue_1_relic_p10"], {}, operator=sniper)
    assert abs(on.atk_pct - 0.4) < 1e-9
    assert abs(on.def_pct + 0.4) < 1e-9
    assert abs(on.aspd - 30) < 1e-9
    assert abs(off.atk_pct) < 1e-9
    assert abs(off.def_pct) < 1e-9


def test_shared_gold_like_conditions():
    on = build_conditional_relic_modifiers(
        ["rogue_1_relic_q26", "rogue_1_relic_q27", "rogue_1_relic_q28"],
        {
            "rogue_1_relic_q26": {"gold": 25},
            "rogue_1_relic_q27": {"gold": 25},
            "rogue_1_relic_q28": {"gold": 25},
        },
    )
    # 5*3 + 5*5 + 5*7 = 15+25+35 = 75
    assert abs(on.aspd - 75) < 1e-6


def test_outer_buffs_nonzero():
    from app.combat.relics import get_outer_buff

    b = get_outer_buff("rogue_1")
    assert b is not None
    assert b["atk_pct"] > 0
    assert b["hp_pct"] > 0
    assert b["def_pct"] > 0


def test_parse_relic_text_negative():
    from app.combat.relics import parse_relic_text

    m = parse_relic_text("折戟", "所有【近卫】干员的防御力-40%，但攻击力+40%，攻击速度+30")
    assert abs(m.def_pct + 0.4) < 1e-9
    assert abs(m.atk_pct - 0.4) < 1e-9
    assert abs(m.aspd - 30) < 1e-9
