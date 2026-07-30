"""主题敌人同步：level ID 转换、关卡 JSON 解析。"""
from pathlib import Path

from app.data.theme_enemy_sync import (
    collect_theme_level_ids,
    enemies_from_level_json,
    level_id_to_rel_path,
    local_level_path,
)


class TestLevelIdToRelPath:
    def test_standard_roguelike_path(self):
        rel = level_id_to_rel_path("Obt/Roguelike/RO1/level_rogue1_1-1")
        assert rel == "zh_CN/gamedata/levels/obt/roguelike/ro1/level_rogue1_1-1.json"

    def test_replacer_path(self):
        rel = level_id_to_rel_path("Obt/Roguelike/RO4/LevelReplacers/level_rogue4_1-1_r1")
        assert rel == (
            "zh_CN/gamedata/levels/obt/roguelike/ro4/levelreplacers/"
            "level_rogue4_1-1_r1.json"
        )

    def test_backslash_path(self):
        rel = level_id_to_rel_path("Obt\\Roguelike\\RO1\\level_rogue1_1-1")
        assert rel == "zh_CN/gamedata/levels/obt/roguelike/ro1/level_rogue1_1-1.json"

    def test_no_json_extension_appended(self):
        rel = level_id_to_rel_path("Obt/Roguelike/RO1/level_rogue1_2-3")
        assert rel.endswith(".json")

    def test_no_roguelike_fallback_regex(self):
        # 没有 roguelike 目录但文件名符合 level_rogue 模式
        rel = level_id_to_rel_path("Some/Path/level_rogue3_boss_5")
        assert rel == "zh_CN/gamedata/levels/obt/roguelike/ro3/level_rogue3_boss_5.json"

    def test_no_roguelike_fallback_without_rogue_prefix(self):
        rel = level_id_to_rel_path("Some/Path/level_main_01-07")
        assert rel is None

    def test_empty_returns_none(self):
        assert level_id_to_rel_path("") is None
        assert level_id_to_rel_path(None) is None  # type: ignore[arg-type]

    def test_already_ends_with_json(self):
        rel = level_id_to_rel_path("Obt/Roguelike/RO1/level_rogue1_1-1.json")
        assert rel == "zh_CN/gamedata/levels/obt/roguelike/ro1/level_rogue1_1-1.json"

    def test_multiple_roguelike_segments(self):
        # 多个 roguelike 目录段：取第一个 roguelike 之后的
        rel = level_id_to_rel_path("Obt/Roguelike/RO2/level_rogue2_deep_3")
        assert rel == "zh_CN/gamedata/levels/obt/roguelike/ro2/level_rogue2_deep_3.json"


class TestEnemiesFromLevelJson:
    def test_from_db_refs(self):
        data = {
            "enemyDbRefs": [
                {"id": "enemy_1001"},
                {"id": "enemy_1002"},
            ]
        }
        result = enemies_from_level_json(data)
        assert result == {"enemy_1001", "enemy_1002"}

    def test_from_enemies_strings(self):
        data = {"enemies": ["enemy_2001", "enemy_2002"]}
        result = enemies_from_level_json(data)
        assert result == {"enemy_2001", "enemy_2002"}

    def test_from_enemies_dicts(self):
        data = {
            "enemies": [
                {"id": "enemy_3001"},
                {"id": "enemy_3002", "name": "Boss"},
            ]
        }
        result = enemies_from_level_json(data)
        assert result == {"enemy_3001", "enemy_3002"}

    def test_combined_sources(self):
        data = {
            "enemyDbRefs": [{"id": "enemy_1001"}],
            "enemies": ["enemy_2001", {"id": "enemy_3001"}],
        }
        result = enemies_from_level_json(data)
        assert result == {"enemy_1001", "enemy_2001", "enemy_3001"}

    def test_empty_json(self):
        assert enemies_from_level_json({}) == set()

    def test_skips_invalid_refs(self):
        data = {
            "enemyDbRefs": [{"name": "no_id"}, {}],
            "enemies": [{}, "not_a_dict_but_string", 123],
        }
        result = enemies_from_level_json(data)
        # string "not_a_dict_but_string" IS valid (enemies can be strings)
        assert "not_a_dict_but_string" in result
        # dict with no "id" key is skipped
        assert len([x for x in result if isinstance(x, dict)]) == 0


class TestCollectThemeLevelIds:
    def test_from_stages(self):
        detail = {
            "stages": {
                "stage1": {"levelId": "Obt/Roguelike/RO1/level_rogue1_1-1"},
                "stage2": {"levelId": "Obt/Roguelike/RO1/level_rogue1_1-2"},
            }
        }
        result = collect_theme_level_ids(detail)
        assert result == {
            "Obt/Roguelike/RO1/level_rogue1_1-1",
            "Obt/Roguelike/RO1/level_rogue1_1-2",
        }

    def test_with_replace_ids(self):
        detail = {
            "stages": {
                "stage1": {
                    "levelId": "Obt/Roguelike/RO1/level_rogue1_1-1",
                    "levelReplaceIds": ["Obt/Roguelike/RO1/level_rogue1_1-1_r1"],
                }
            }
        }
        result = collect_theme_level_ids(detail)
        assert "Obt/Roguelike/RO1/level_rogue1_1-1_r1" in result

    def test_empty_stages(self):
        assert collect_theme_level_ids({"stages": {}}) == set()

    def test_skips_non_dict_stages(self):
        detail = {
            "stages": {
                "ok": {"levelId": "Obt/Roguelike/RO1/level_1"},
                "bad": "not_a_dict",
            }
        }
        result = collect_theme_level_ids(detail)
        assert result == {"Obt/Roguelike/RO1/level_1"}


class TestLocalLevelPath:
    def test_strips_zh_cn_prefix(self, monkeypatch):
        # Windows 上必须以盘符开头才是绝对路径
        fake_root = Path("C:/fake/gamedata")
        # gamedata_path 是只读 property，改为设置底层 GAMEDATA_DIR 字段（绝对路径）
        monkeypatch.setattr(
            "app.data.theme_enemy_sync.settings.GAMEDATA_DIR", str(fake_root)
        )
        path = local_level_path(
            "zh_CN/gamedata/levels/obt/roguelike/ro1/level.json"
        )
        assert path == fake_root / "levels/obt/roguelike/ro1/level.json"

    def test_without_prefix_relative(self, monkeypatch):
        # Windows 上必须以盘符开头才是绝对路径
        fake_root = Path("C:/fake/gamedata")
        monkeypatch.setattr(
            "app.data.theme_enemy_sync.settings.GAMEDATA_DIR", str(fake_root)
        )
        path = local_level_path("levels/obt/roguelike/ro1/level.json")
        assert path == fake_root / "levels/obt/roguelike/ro1/level.json"

    def test_backslash_suffix_stripped(self, monkeypatch):
        # Windows 上必须以盘符开头才是绝对路径
        fake_root = Path("C:/fake/gamedata")
        monkeypatch.setattr(
            "app.data.theme_enemy_sync.settings.GAMEDATA_DIR", str(fake_root)
        )
        path = local_level_path(
            "zh_CN\\gamedata\\levels\\obt\\roguelike\\ro1\\level.json"
        )
        assert path == fake_root / "levels/obt/roguelike/ro1/level.json"
