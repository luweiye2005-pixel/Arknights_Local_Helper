"""属性插值与面板计算单元测试。"""
from app.combat.attributes import calc_operator_panel, favor_bonus, interpolate_frames


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
