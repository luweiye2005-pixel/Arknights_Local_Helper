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
    # potential 5 → *1.10；module +10 flat +10%
    panel = calc_operator_panel(
        op, elite=0, level=1, favor_percent=0, potential=5, module_atk_flat=10, module_atk_pct=0.1
    )
    # atk = 100 * 1.1 * 1.1 + 10 = 131
    assert abs(panel["atk"] - 131) < 1e-6


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
    """atk 值 < 2 时按 1+value 处理（如 0.8 → 1.8）。"""
    levels = [
        {
            "blackboard": [
                {"key": "atk", "value": 0.8},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_scale"] - 1.8) < 1e-6


def test_skill_atk_key_large_value():
    """atk 一律加算：3.0 → 1+3.0=4.0 (+300%)。如乌尔比安三技能 atk=2.6→+260%。"""
    levels = [
        {
            "blackboard": [
                {"key": "atk", "value": 3.0},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_scale"] - 4.0) < 1e-6


def test_skill_damage_scale_key():
    levels = [
        {
            "blackboard": [
                {"key": "damage_scale", "value": 1.5},
            ],
        }
    ]
    info = skill_multiplier_and_duration(levels, 1)
    assert abs(info["atk_scale"] - 1.5) < 1e-6


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
