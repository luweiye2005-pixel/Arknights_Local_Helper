"""属性插值与面板计算单元测试。"""
from app.combat.attributes import calc_operator_panel, favor_bonus, interpolate_frames, skill_multiplier_and_duration


def test_interpolate_empty():
    out = interpolate_frames([], 1)
    assert out["atk"] == 0
    assert out["attackSpeed"] == 100


def test_interpolate_endpoints():
    frames = [
        {"level": 1, "data": {"atk": 100, "maxHp": 1000, "def": 50, "magicResistance": 0, "attackSpeed": 100, "baseAttackTime": 1.0}},
        {"level": 80, "data": {"atk": 500, "maxHp": 2000, "def": 200, "magicResistance": 10, "attackSpeed": 100, "baseAttackTime": 1.0}},
    ]
    lo = interpolate_frames(frames, 1)
    hi = interpolate_frames(frames, 80)
    mid = interpolate_frames(frames, 40)
    assert abs(lo["atk"] - 100) < 1e-6
    assert abs(hi["atk"] - 500) < 1e-6
    expected = 100 + (500 - 100) * (40 - 1) / (80 - 1)
    assert abs(mid["atk"] - expected) < 1e-6


def test_favor_bonus_percent():
    frames = [
        {"level": 0, "data": {"atk": 0, "maxHp": 0, "def": 0}},
        {"level": 50, "data": {"atk": 50, "maxHp": 200, "def": 20}},
    ]
    half = favor_bonus(frames, 50)
    full = favor_bonus(frames, 100)
    assert abs(half["atk"] - 25) < 1e-6
    assert abs(full["atk"] - 50) < 1e-6


def test_calc_operator_panel_basic():
    op = {
        "raw_phases": [
            {
                "attributesKeyFrames": [
                    {"level": 1, "data": {"atk": 100, "maxHp": 1000, "def": 50, "magicResistance": 0, "attackSpeed": 100, "baseAttackTime": 1.2}},
                    {"level": 50, "data": {"atk": 300, "maxHp": 1500, "def": 100, "magicResistance": 5, "attackSpeed": 100, "baseAttackTime": 1.2}},
                ]
            }
        ],
        "favor_key_frames": [
            {"level": 0, "data": {"atk": 0, "maxHp": 0, "def": 0}},
            {"level": 50, "data": {"atk": 20, "maxHp": 100, "def": 10}},
        ],
    }
    panel = calc_operator_panel(op, elite=0, level=50, favor_percent=100, potential=0)
    assert panel["atk"] == 320  # 300 + 20 favor
    assert panel["hp"] == 1600
    assert abs(panel["base_attack_time"] - 1.2) < 1e-6


def test_calc_operator_panel_module_and_potential():
    op = {
        "raw_phases": [
            {
                "attributesKeyFrames": [
                    {"level": 1, "data": {"atk": 100, "maxHp": 1000, "def": 0, "magicResistance": 0, "attackSpeed": 100, "baseAttackTime": 1}},
                    {"level": 1, "data": {"atk": 100, "maxHp": 1000, "def": 0, "magicResistance": 0, "attackSpeed": 100, "baseAttackTime": 1}},
                ]
            }
        ],
        "favor_key_frames": [],
    }
    # 潜能加成来自 potential_ranks；没有潜能数据时不得凭潜能档位虚构百分比。
    panel = calc_operator_panel(
        op, elite=0, level=1, favor_percent=0, potential=5, module_atk_flat=10, module_atk_pct=0.1
    )
    # atk = 100 * 1.1 + 10 = 120
    assert abs(panel["atk"] - 120) < 1e-6


# ---------- skill_multiplier_and_duration ----------

def test_skill_empty_levels():
    info = skill_multiplier_and_duration([], 7)
    assert info["atk_scale"] == 1.0
    assert info["duration"] == 0.0
    assert info["name"] is None


def test_skill_atk_scale_key():
    levels = [
        {
            "name": "强力击",
            "duration": 0,
            "description": "描述",
            "blackboard": [
                {"key": "atk_scale", "value": 2.0},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_scale"] - 2.0) < 1e-6
    assert info["name"] == "强力击"


def test_skill_attack_atk_scale_key():
    """blackboard 中 key 为 attack@atk_scale 时也应能提取。"""
    levels = [
        {
            "blackboard": [
                {"key": "attack@atk_scale", "value": 2.5},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_scale"] - 2.5) < 1e-6


def test_skill_atk_key_small_value():
    """atk 是面板加算区，不应混入单次命中倍率。"""
    levels = [
        {
            "blackboard": [
                {"key": "atk", "value": 0.8},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_scale"] - 1.0) < 1e-6
    assert abs(info["atk_pct"] - 0.8) < 1e-6


def test_skill_atk_key_large_value():
    """较大的 atk 仍是面板加算百分比，如 3.0 表示 +300%。"""
    levels = [
        {
            "blackboard": [
                {"key": "atk", "value": 3.0},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_scale"] - 1.0) < 1e-6
    assert abs(info["atk_pct"] - 3.0) < 1e-6


def test_skill_damage_scale_key():
    levels = [
        {
            "blackboard": [
                {"key": "damage_scale", "value": 1.5},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_scale"] - 1.0) < 1e-6
    assert abs(info["damage_scale"] - 1.5) < 1e-6


def test_skill_duration_positive():
    levels = [{"blackboard": [], "duration": 30, "name": "技能A"}]
    info = skill_multiplier_and_duration(levels, 1)
    assert info["duration"] == 30


def test_skill_duration_negative_clamped():
    """负 duration 被钳制为 0。"""
    levels = [{"blackboard": [], "duration": -5}]
    info = skill_multiplier_and_duration(levels, 1)
    assert info["duration"] == 0


def test_skill_level_out_of_range():
    """skill_level 超出列表范围时取最后一个。"""
    levels = [
        {"blackboard": [{"key": "atk_scale", "value": 1.2}], "duration": 10},
        {"blackboard": [{"key": "atk_scale", "value": 2.0}], "duration": 20},
    ]
    info = skill_multiplier_and_duration(levels, 99)
    assert abs(info["atk_scale"] - 2.0) < 1e-6
    assert info["duration"] == 20


def test_skill_blackboard_no_scale_keys():
    """blackboard 中无任何倍率 key 时返回默认 1.0。"""
    levels = [
        {
            "blackboard": [
                {"key": "cnt", "value": 3},
                {"key": "range", "value": 1.5},
            ],
            "duration": 5,
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_scale"] - 1.0) < 1e-6
    assert info["duration"] == 5


def test_ulpianus_skill_3_self_buffs_are_not_enemy_effects():
    """后半句提到敌人时，前半句的自身属性标签仍应归属于干员。"""
    levels = [
        {
            "name": "必须开辟的通路",
            "duration": 25,
            "description": (
                "最大生命值<@ba.vup>+{max_hp:0%}</>，"
                "攻击力<@ba.vup>+{atk:0%}</>，立即朝面前扔出一个船锚，"
                "并对周围所有敌人造成攻击力<@ba.vup>{atk_scale:0%}</>的物理伤害"
            ),
            "blackboard": [
                {"key": "max_hp", "value": 0.8},
                {"key": "atk", "value": 2.6},
                {"key": "atk_scale", "value": 1.6},
            ],
        }
    ]

    info = skill_multiplier_and_duration(levels, 1)
    assert info["hp_pct"] == 0.8
    assert info["atk_pct"] == 2.6
    assert info["atk_scale"] == 1.6
    assert info["enemy_effects"]["hp_pct"] == 0
    assert info["enemy_effects"]["atk_pct"] == 0


def test_positive_self_buffs_stay_self_when_description_mentions_enemies():
    cases = [
        (
            "每击中一个敌人获得攻击力<@ba.vup>+{atk:0%}</>",
            {"key": "atk", "value": 0.3},
            "atk_pct",
        ),
        (
            "攻击力<@ba.vup>+{atk:0%}</>，有地面敌人处于范围内时触发其他效果",
            {"key": "atk", "value": 0.5},
            "atk_pct",
        ),
        (
            "自身更容易受到敌人攻击，生命上限<@ba.vup>+{max_hp:0%}</>",
            {"key": "max_hp", "value": 0.7},
            "hp_pct",
        ),
    ]
    for description, blackboard, field in cases:
        info = skill_multiplier_and_duration(
            [{"description": description, "blackboard": [blackboard]}],
            1,
        )
        assert info[field] == blackboard["value"]
        assert all(value == 0 for value in info["enemy_effects"].values())


def test_nested_enemy_flat_def_debuff_is_parsed_from_exact_placeholder():
    description = (
        "\u5730\u9762\u654c\u4eba\u7ecf\u8fc7\u65f6\u79fb\u52a8\u901f\u5ea6"
        "{attack@move_speed:0%}\u3001\u9632\u5fa1\u529b{attack@def}"
    )
    info = skill_multiplier_and_duration(
        [{"description": description, "blackboard": [
            {"key": "attack@def", "value": -220},
            {"key": "attack@move_speed", "value": -0.4},
        ]}],
        1,
    )
    assert info["enemy_effects"]["def_flat"] == -220
    assert info["def_pct"] == 0


def test_nested_summon_attribute_is_not_applied_to_operator_or_enemy():
    description = "Mon3tr\u7684\u653b\u51fb\u529b+{attack@atk:0%}"
    info = skill_multiplier_and_duration(
        [{"description": description, "blackboard": [
            {"key": "attack@atk", "value": 1.9},
        ]}],
        1,
    )
    assert info["atk_pct"] == 0
    assert all(value == 0 for value in info["enemy_effects"].values())


def test_recurring_attack_scale_is_preferred_over_terminal_extra_packet():
    info = skill_multiplier_and_duration(
        [{"description": (
            "\u6bcf\u6b21\u653b\u51fb\u9020\u6210{attack@atk_scale:0%}"
            "\uff0c\u6280\u80fd\u7ed3\u675f\u65f6\u9020\u6210{atk_scale:0%}"
        ), "blackboard": [
            {"key": "attack@atk_scale", "value": 1.3},
            {"key": "atk_scale", "value": 3.0},
        ]}],
        1,
    )
    assert info["atk_scale"] == 1.3
