"""MySQL 辅助逻辑（不依赖真实业务数据变更）。"""
from app.data.mysql_db import _parse_rule_desc_mods


def test_parse_rule_desc_damage_taken():
    mods = _parse_rule_desc_mods("rogue_x", 10, "所有敌人受到的物理与法术伤害降低10%")
    attrs = {(m["target"], m["attr"], m["value"]) for m in mods}
    assert ("enemy", "damage_taken_phys_pct", -0.1) in attrs
    assert ("enemy", "damage_taken_arts_pct", -0.1) in attrs


def test_parse_rule_desc_enemy_atk():
    mods = _parse_rule_desc_mods("rogue_x", 5, "敌人攻击力提升15%")
    assert any(m["attr"] == "atk_pct" and abs(m["value"] - 0.15) < 1e-6 for m in mods)


def test_parse_rule_desc_empty():
    assert _parse_rule_desc_mods("rogue_x", 0, "") == []
