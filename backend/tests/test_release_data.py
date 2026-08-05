"""使用真实 release_data/data.json.gz 的 API 契约测试。

设置 DATA_BACKEND=json，验证搜索、详情、panel 计算链路。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "release_data"

# 强制 JSON 后端
os.environ["DATA_BACKEND"] = "json"
os.environ["OFFLINE_DATA_DIR"] = str(RELEASE)
os.environ["ICONS_DIR"] = str(ROOT / "data" / "icons")

# 清除已缓存的 db 模块，让它重新选择 json 后端
for key in list(sys.modules):
    if key.startswith("app.data"):
        del sys.modules[key]


def _ensure_release_data():
    if not (RELEASE / "data.json.gz").is_file():
        pytest.skip("release_data/data.json.gz 不存在")


class TestReleaseDataRead:
    """离线数据包基础读取测试。"""

    def test_init_schema_loads(self):
        _ensure_release_data()
        from app.data import db as gdb
        gdb.init_schema()
        counts = gdb.db_counts()
        assert counts["operators"] >= 400
        assert counts["enemies"] >= 1500
        assert counts["relics"] >= 1700

    def test_search_operators(self):
        _ensure_release_data()
        from app.data import db as gdb
        items = gdb.search_operators("阿米娅", limit=10)
        assert len(items) >= 1
        assert any("阿米娅" in (o.get("name") or "") for o in items)

    def test_get_operator_detail(self):
        _ensure_release_data()
        from app.data import db as gdb
        op = gdb.get_operator_detail("char_002_amiya")
        assert op is not None
        assert op.get("name") is not None
        assert op.get("rarity") is not None
        assert isinstance(op.get("phases"), list)

    def test_get_operator_skills(self):
        _ensure_release_data()
        from app.data import db as gdb
        skills = gdb.get_operator_skills("char_002_amiya")
        assert isinstance(skills, list)
        assert len(skills) >= 1

    def test_search_enemies(self):
        _ensure_release_data()
        from app.data import db as gdb
        items = gdb.search_enemies("", limit=10)
        assert len(items) >= 1

    def test_get_enemy_row(self):
        _ensure_release_data()
        from app.data import db as gdb
        # 找一个真实敌人 ID
        items = gdb.search_enemies("", limit=1)
        if items:
            enemy = gdb.get_enemy_row(items[0]["id"], level=0)
            assert enemy is not None

    def test_search_relics(self):
        _ensure_release_data()
        from app.data import db as gdb
        items = gdb.search_relics(limit=200)
        assert len(items) >= 1

    def test_list_themes(self):
        _ensure_release_data()
        from app.data import db as gdb
        themes = gdb.list_themes_db()
        assert len(themes) >= 6
        ids = {t["id"] for t in themes}
        assert "rogue_1" in ids
        assert "rogue_6" in ids

    def test_relic_rules_have_no_pending(self):
        _ensure_release_data()
        from app.data import db as gdb
        rules = gdb.get_relic_rule_rows(
            [r["id"] for r in gdb.search_relics(limit=100)],
            0,
        )
        for r in rules:
            if r.get("calculation_status") == "active":
                assert r.get("review_status") == "approved", (
                    f"pending rule: {r['relic_id']}.{r['attr']}"
                )


class TestPanelCalculation:
    """端到端 panel 计算测试。"""

    def _find_operator_id(self):
        from app.data import db as gdb
        items = gdb.search_operators("", limit=10)
        return items[0]["id"] if items else None

    def _find_enemy_id(self, theme_id=None):
        from app.data import db as gdb
        items = gdb.search_enemies("", limit=10, theme_id=theme_id)
        return items[0]["id"] if items else None

    def _find_relic_ids(self, theme_id, count=3):
        from app.data import db as gdb
        items = gdb.search_relics(theme=theme_id, limit=count)
        return [r["id"] for r in items]

    def test_panel_operator_only(self):
        """仅计算干员面板（无敌人、无藏品）。"""
        _ensure_release_data()
        from app.combat.panel import calculate_panel
        op_id = self._find_operator_id()
        if not op_id:
            pytest.skip("无干员数据")
        result = calculate_panel({
            "operator_id": op_id,
            "elite": 2, "level": 90, "favor_percent": 200,
            "potential": 0, "damage_type": "PHYS",
        })
        assert result.get("base_panel") is not None
        assert result["base_panel"]["atk"] > 0

    @pytest.mark.parametrize("theme_id", ["rogue_1", "rogue_3", "rogue_6"])
    def test_panel_with_theme(self, theme_id):
        """计算不同主题的干员+敌人+藏品面板。"""
        _ensure_release_data()
        from app.combat.panel import calculate_panel
        from app.data import db as gdb
        op_id = self._find_operator_id()
        enemy_id = self._find_enemy_id(theme_id)
        relic_ids = self._find_relic_ids(theme_id, 3)
        if not op_id or not enemy_id:
            pytest.skip(f"缺少 {theme_id} 数据")
        themes = gdb.list_themes_db()
        theme_exists = any(t["id"] == theme_id for t in themes)
        if not theme_exists:
            pytest.skip(f"主题 {theme_id} 不在离线数据中")
        result = calculate_panel({
            "operator_id": op_id,
            "enemy_id": enemy_id,
            "elite": 2, "level": 50, "favor_percent": 100,
            "potential": 0, "damage_type": "PHYS",
            "theme_id": theme_id,
            "equivalent_grade": 0,
            "relic_ids": relic_ids,
        })
        assert result.get("final_panel") is not None
        assert result.get("enemy_final_panel") is not None
        assert isinstance(result.get("relic_contributions"), dict)
        # 验证结算输出结构
        damage_factors = result["relic_contributions"].get("damage_factors", {})
        assert "PHYS" in damage_factors
        assert "product" in damage_factors["PHYS"]

    def test_panel_all_damage_types(self):
        """验证四种伤害类型均可计算。"""
        _ensure_release_data()
        from app.combat.panel import calculate_panel
        op_id = self._find_operator_id()
        if not op_id:
            pytest.skip("无干员数据")
        for dtype in ("PHYS", "MAGIC", "TRUE", "ELEMENTAL"):
            result = calculate_panel({
                "operator_id": op_id,
                "elite": 2, "level": 90,
                "damage_type": dtype,
            })
            assert result.get("base_panel") is not None
