"""面板计算（mock MySQL）。"""
from unittest.mock import patch

from app.combat.panel import calculate_panel


def _fake_operator():
    return {
        "id": "char_test",
        "name": "测试干员",
        "profession_cn": "近卫",
        "rarity": 6,
        "modules": [
            {
                "id": "mod1",
                "name": "模组X",
                "type": "X",
                "max_level": 3,
                "levels": [
                    {"level": 1, "atk": 10, "atk_pct": 0, "attack_speed": 0},
                    {"level": 3, "atk": 30, "atk_pct": 0.05, "attack_speed": 5},
                ],
            }
        ],
        "raw_phases": [
            {"attributesKeyFrames": []},
            {"attributesKeyFrames": []},
            {
                "attributesKeyFrames": [
                    {
                        "level": 1,
                        "data": {
                            "atk": 200,
                            "maxHp": 2000,
                            "def": 100,
                            "magicResistance": 0,
                            "attackSpeed": 100,
                            "baseAttackTime": 1.0,
                        },
                    },
                    {
                        "level": 90,
                        "data": {
                            "atk": 500,
                            "maxHp": 3000,
                            "def": 200,
                            "magicResistance": 10,
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


def test_calculate_panel_missing_operator():
    with patch("app.combat.panel.gdb.get_operator_detail", return_value=None):
        try:
            calculate_panel({"operator_id": "nope"})
            assert False, "should raise"
        except ValueError as e:
            assert "未找到干员" in str(e)


def test_calculate_panel_requires_operator_or_enemy():
    try:
        calculate_panel({"relic_ids": []})
        assert False, "should raise"
    except ValueError as e:
        assert "干员或敌人" in str(e)


def test_calculate_panel_enemy_only():
    enemy = {
        "id": "enemy_1",
        "name": "测试怪",
        "enemy_level": "NORMAL",
        "level_index": 0,
        "attributes": {
            "hp": 1000,
            "atk": 100,
            "def": 50,
            "magic_resistance": 10,
            "attack_speed": 100,
            "move_speed": 1,
            "range_radius": 1,
            "damage_type": "PHYSIC",
        },
        "difficulty_mods": [{"attr": "hp_pct", "value": 0.1}],
    }
    with (
        patch("app.combat.panel.gdb.get_enemy_row", return_value=enemy),
        patch(
            "app.combat.panel.build_enemy_relic_modifiers",
            return_value=__import__(
                "app.combat.relics", fromlist=["EnemyStatModifiers"]
            ).EnemyStatModifiers(hp_pct=0.25, notes=["t"]),
        ),
        patch("app.combat.panel.gdb.resolve_relic_for_grade", return_value=None),
        patch("app.combat.panel.gdb.get_relic_row", return_value=None),
    ):
        result = calculate_panel(
            {
                "enemy_id": "enemy_1",
                "theme_id": "rogue_1",
                "equivalent_grade": 2,
                "relic_ids": ["r1"],
            }
        )
    assert result["operator"] is None
    assert result["final_panel"] is None
    assert result["enemy"]["name"] == "测试怪"
    # 1000 * (1+0.25) — difficulty already baked into get_enemy_row attrs
    assert abs(result["enemy_final_panel"]["hp"] - 1250) < 1e-6


def test_calculate_panel_with_module_and_relics():
    op = _fake_operator()

    def resolve(rid, grade, conn=None):
        return {"id": rid, "name": f"遗物{rid}"}

    with (
        patch("app.combat.panel.gdb.get_operator_detail", return_value=op),
        patch("app.combat.panel.gdb.resolve_relic_for_grade", side_effect=resolve),
        patch(
            "app.combat.panel.build_relic_modifiers",
            return_value=__import__("app.combat.relics", fromlist=["CombatModifiers"]).CombatModifiers(
                atk_pct=0.2, aspd=10, notes=["t"]
            ),
        ),
    ):
        result = calculate_panel(
            {
                "operator_id": "char_test",
                "elite": 2,
                "level": 90,
                "favor_percent": 100,
                "potential": 0,
                "module_id": "mod1",
                "module_level": 3,
                "relic_ids": ["r1"],
                "theme_id": "rogue_1",
                "equivalent_grade": 3,
            }
        )

    assert result["operator"]["name"] == "测试干员"
    assert result["module"]["atk"] == 30
    # base atk 500 * 1.05 + 30 = 555；再 *1.2 relic
    assert abs(result["base_panel"]["atk"] - 555) < 1e-6
    assert abs(result["final_panel"]["atk"] - 555 * 1.2) < 1e-6
    assert abs(result["final_panel"]["attack_speed"] - 115) < 1e-6  # 100+5+10
    assert result["config"]["equivalent_grade"] == 3
    assert result["relics_applied"][0]["id"] == "r1"
