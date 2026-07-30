"""游戏数据加载与索引。"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import settings

# 职业中文名映射
PROFESSION_CN = {
    "PIONEER": "先锋",
    "WARRIOR": "近卫",
    "TANK": "重装",
    "SNIPER": "狙击",
    "CASTER": "术师",
    "MEDIC": "医疗",
    "SUPPORT": "辅助",
    "SPECIAL": "特种",
    "TOKEN": "召唤物",
    "TRAP": "装置",
}

POSITION_CN = {
    "MELEE": "近战",
    "RANGED": "远程",
}

DAMAGE_TYPE_CN = {
    "PHYS": "物理",
    "MAGIC": "法术",
    "HEAL": "治疗",
}


@dataclass
class GameDataStore:
    """本地 JSON 数据缓存。"""

    character_table: dict[str, Any] = field(default_factory=dict)
    enemy_handbook: dict[str, Any] = field(default_factory=dict)
    enemy_database: dict[str, Any] = field(default_factory=dict)
    skill_table: dict[str, Any] = field(default_factory=dict)
    uni_equip_table: dict[str, Any] = field(default_factory=dict)
    battle_equip_table: dict[str, Any] = field(default_factory=dict)
    roguelike_topic_table: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    relics: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def load(self) -> None:
        with self._lock:
            root = settings.gamedata_path
            root.mkdir(parents=True, exist_ok=True)
            self.character_table = _read_json(root / "character_table.json")
            self.enemy_handbook = _read_json(root / "enemy_handbook_table.json")
            self.enemy_database = _read_json(root / "enemy_database.json")
            self.skill_table = _read_json(root / "skill_table.json")
            self.uni_equip_table = _read_json(root / "uniequip_table.json")
            self.battle_equip_table = _read_json(root / "battle_equip_table.json")
            self.roguelike_topic_table = _read_json(root / "roguelike_topic_table.json")
            self.meta = _read_json(root / "meta.json")
            self.relics = self._build_relics()
            self.counts = {
                "operators": len(self.list_operators(limit=99999)),
                "enemies": len(self.list_enemies(limit=99999)),
                "relics": len(self.relics),
            }
            logger.info(
                f"GameData loaded: operators={self.counts['operators']}, "
                f"enemies={self.counts['enemies']}, relics={self.counts['relics']}"
            )

    def list_operators(self, q: str | None = None, limit: int = 50) -> list[dict]:
        items = []
        for cid, raw in self.character_table.items():
            if not isinstance(raw, dict):
                continue
            if not cid.startswith("char_"):
                continue
            # 过滤不可获得 / 召唤物类
            if raw.get("isNotObtainable"):
                continue
            profession = raw.get("profession") or ""
            if profession in {"TOKEN", "TRAP"}:
                continue
            name = raw.get("name") or cid
            appellation = (raw.get("appellation") or "").lower()
            qn = (q or "").strip().lower()
            if qn:
                hay = f"{name} {cid} {appellation} {PROFESSION_CN.get(profession, '')}".lower()
                if qn not in hay:
                    continue
            position = (raw.get("position") or "").upper() or None
            items.append(
                {
                    "id": cid,
                    "name": name,
                    "rarity": _rarity(raw),
                    "profession": profession,
                    "profession_cn": PROFESSION_CN.get(profession, profession),
                    "sub_profession": raw.get("subProfessionId"),
                    "position": position,
                    "position_cn": POSITION_CN.get(position or "", position),
                }
            )
        items.sort(key=lambda x: (-(x["rarity"] or 0), x["name"]))
        return items[:limit]

    def get_operator(self, operator_id: str) -> dict | None:
        raw = self.character_table.get(operator_id)
        if not raw:
            return None
        skills = []
        for s in raw.get("skills") or []:
            sid = s.get("skillId")
            skill_raw = self.skill_table.get(sid) if sid else None
            levels = []
            if skill_raw:
                for i, lv in enumerate(skill_raw.get("levels") or []):
                    levels.append(
                        {
                            "level": i + 1,
                            "name": lv.get("name"),
                            "description": lv.get("description"),
                            "skill_type": lv.get("skillType"),
                            "duration": lv.get("duration"),
                            "sp_data": lv.get("spData"),
                            "blackboard": lv.get("blackboard") or [],
                            "prefab": lv.get("prefabId"),
                        }
                    )
            skills.append({"skill_id": sid, "unlock": s.get("unlockCond"), "levels": levels})

        modules = self._build_modules(operator_id)

        phases = []
        for i, ph in enumerate(raw.get("phases") or []):
            frames = ph.get("attributesKeyFrames") or []
            max_lv = frames[-1]["level"] if frames else 1
            phases.append(
                {
                    "elite": i,
                    "max_level": max_lv,
                    "range_id": ph.get("rangeId"),
                }
            )

        position = (raw.get("position") or "").upper() or None
        sub_id = raw.get("subProfessionId")
        sub_cn = None
        try:
            sub_cn = (
                (self.uni_equip_table.get("subProfDict") or {})
                .get(sub_id or "", {})
                .get("subProfessionName")
            )
        except Exception:
            sub_cn = None
        return {
            "id": operator_id,
            "name": raw.get("name"),
            "rarity": _rarity(raw),
            "profession": raw.get("profession"),
            "profession_cn": PROFESSION_CN.get(raw.get("profession") or "", raw.get("profession")),
            "sub_profession": sub_id,
            "sub_profession_cn": sub_cn,
            "position": position,
            "position_cn": POSITION_CN.get(position or "", position),
            "description": raw.get("description"),
            "phases": phases,
            "skills": skills,
            "modules": modules,
            "favor_key_frames": raw.get("favorKeyFrames") or [],
            "potential_ranks": raw.get("potentialRanks") or [],
            "raw_phases": raw.get("phases") or [],
        }

    def list_enemies(self, q: str | None = None, limit: int = 50) -> list[dict]:
        items = []
        # enemy_handbook_table 常见结构: {"enemyData": {...}} 或直接 dict
        handbook = self.enemy_handbook.get("enemyData") or self.enemy_handbook
        if not isinstance(handbook, dict):
            return []
        for eid, raw in handbook.items():
            if not isinstance(raw, dict):
                continue
            name = raw.get("name") or eid
            qn = (q or "").strip().lower()
            if qn and qn not in name.lower() and qn not in eid.lower():
                continue
            items.append(
                {
                    "id": eid,
                    "name": name,
                    "enemy_level": raw.get("enemyLevel") or raw.get("levelType"),
                    "description": (raw.get("description") or "")[:120],
                }
            )
        items.sort(key=lambda x: x["name"])
        return items[:limit]

    def get_enemy(self, enemy_id: str, level: int = 0) -> dict | None:
        handbook = self.enemy_handbook.get("enemyData") or self.enemy_handbook
        info = handbook.get(enemy_id) if isinstance(handbook, dict) else None

        # enemy_database.json: {"enemies":[{"Key":"...", "Value":[...]}]}
        stats = None
        enemies_list = self.enemy_database.get("enemies") or []
        for entry in enemies_list:
            if entry.get("Key") == enemy_id:
                values = entry.get("Value") or []
                if values:
                    idx = min(max(level, 0), len(values) - 1)
                    stats = values[idx]
                break

        if info is None and stats is None:
            return None

        attrs = {}
        if stats:
            # Value 项可能是 {"level":0,"enemyData":{...}}
            ed = stats.get("enemyData") or stats
            attr = (ed.get("attributes") or {}) if isinstance(ed, dict) else {}
            attrs = {
                "hp": _attr_m(attr, "maxHp"),
                "atk": _attr_m(attr, "atk"),
                "def": _attr_m(attr, "def"),
                "magic_resistance": _attr_m(attr, "magicResistance"),
                "move_speed": _attr_m(attr, "moveSpeed"),
                "attack_speed": _attr_m(attr, "attackSpeed"),
                "range_radius": _attr_m(attr, "rangeRadius"),
                "damage_type": _guess_damage_type(ed),
            }

        return {
            "id": enemy_id,
            "name": (info or {}).get("name") or enemy_id,
            "description": (info or {}).get("description"),
            "level_index": level,
            "attributes": attrs,
            "raw_level_count": _enemy_level_count(self.enemy_database, enemy_id),
        }

    def list_relics(self, theme: str | None = None, q: str | None = None, limit: int = 200) -> list[dict]:
        items = self.relics
        if theme:
            items = [r for r in items if r.get("theme") == theme]
        if q:
            ql = q.lower()
            items = [
                r
                for r in items
                if ql in (r.get("name") or "").lower() or ql in (r.get("id") or "").lower()
            ]
        return items[:limit]

    def get_relic(self, relic_id: str) -> dict | None:
        for r in self.relics:
            if r["id"] == relic_id:
                return r
        return None

    def list_themes(self) -> list[dict]:
        topics = self.roguelike_topic_table.get("topics") or {}
        result = []
        for tid, t in topics.items():
            result.append(
                {
                    "id": tid,
                    "name": t.get("name") or tid,
                    "start_time": t.get("startTime"),
                }
            )
        # 也从已解析遗物里补全
        seen = {t["id"] for t in result}
        for r in self.relics:
            th = r.get("theme")
            if th and th not in seen:
                result.append({"id": th, "name": th})
                seen.add(th)
        return result

    def _build_relics(self) -> list[dict]:
        table = self.roguelike_topic_table
        details = table.get("details") or {}
        relics: list[dict] = []
        seen: set[str] = set()
        for theme_id, detail in details.items():
            if not isinstance(detail, dict):
                continue
            items = detail.get("items") or {}
            archive = ((detail.get("archiveComp") or {}).get("relic") or {}).get("relic") or {}
            # 优先 archive 列表；否则扫描 items 中带 relic 特征的
            ids = list(archive.keys()) if archive else [
                iid
                for iid, it in items.items()
                if isinstance(it, dict)
                and (
                    "relic" in iid.lower()
                    or it.get("type") in ("RELIC", "ACTIVE_TOOL", "CAPSULE")
                    or str(it.get("type")).upper() == "RELIC"
                )
            ]
            # 难度升级链里的变体（*_a/_b/_c）也要入库
            for g in (detail.get("difficultyUpgradeRelicGroups") or {}).values():
                if not isinstance(g, dict):
                    continue
                for step in g.get("relicData") or []:
                    if isinstance(step, dict) and step.get("relicId"):
                        ids.append(step["relicId"])
            for rid in ids:
                if rid in seen:
                    continue
                seen.add(rid)
                it = items.get(rid) or {}
                meta = archive.get(rid) or {}
                name = it.get("name") or meta.get("name") or rid
                usage = it.get("usage") or it.get("description") or meta.get("usage") or ""
                icon_id = it.get("iconId") or meta.get("iconId") or rid
                relics.append(
                    {
                        "id": rid,
                        "theme": theme_id,
                        "name": name,
                        "usage": usage,
                        "description": it.get("description") or "",
                        "order_id": meta.get("orderId"),
                        "icon_id": icon_id,
                    }
                )
        return relics

    def _build_modules(self, operator_id: str) -> list[dict]:
        modules = []
        equip_dict = (self.uni_equip_table.get("equipDict") or {}) if self.uni_equip_table else {}
        char_equip = (self.uni_equip_table.get("charEquip") or {}).get(operator_id) or []
        for mid in char_equip:
            m = equip_dict.get(mid) or {}
            type_name = m.get("typeName2")
            if not type_name or str(type_name).upper() == "ORIGINAL":
                continue
            levels = self._module_levels(mid)
            modules.append(
                {
                    "id": mid,
                    "name": m.get("uniEquipName") or mid,
                    "type": type_name,
                    "description": m.get("uniEquipDesc"),
                    "max_level": len(levels) or 1,
                    "levels": levels,
                }
            )
        return modules

    def _module_levels(self, module_id: str) -> list[dict]:
        raw = self.battle_equip_table.get(module_id) or {}
        phases = raw.get("phases") or []
        levels = []
        for i, ph in enumerate(phases):
            bb = {b.get("key"): float(b.get("value") or 0) for b in (ph.get("attributeBlackboard") or []) if isinstance(b, dict)}
            levels.append(
                {
                    "level": int(ph.get("equipLevel") or (i + 1)),
                    "atk": bb.get("atk") or 0.0,
                    "atk_pct": 0.0,
                    "hp": bb.get("max_hp") or bb.get("hp") or 0.0,
                    "defense": bb.get("def") or 0.0,
                    "attack_speed": bb.get("attack_speed") or 0.0,
                    "blackboard": ph.get("attributeBlackboard") or [],
                }
            )
            # 部分模组用 atk 表示加算；若存在 attack@atk_scale 等由 blackboard 保留
            for b in ph.get("attributeBlackboard") or []:
                if not isinstance(b, dict):
                    continue
                key = (b.get("key") or "").lower()
                val = float(b.get("value") or 0)
                if key in {"atk_scale", "attack@atk_scale"} and 0 < val < 5:
                    levels[-1]["atk_pct"] = val if val > 1 else val  # 少见
                if "percent" in key and "atk" in key:
                    levels[-1]["atk_pct"] = val
        if not levels:
            levels = [{"level": 1, "atk": 0, "atk_pct": 0, "hp": 0, "defense": 0, "attack_speed": 0, "blackboard": []}]
        return levels


def _read_json(path: Path) -> dict:
    if not path.exists():
        logger.warning(f"缺少数据文件: {path}")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"_list": data}
    except Exception as e:
        logger.error(f"读取失败 {path}: {e}")
        return {}


def _rarity(raw: dict) -> int:
    # 新版 rarity 可能是 "TIER_6" 或数字
    r = raw.get("rarity")
    if isinstance(r, int):
        return r + 1 if r <= 5 else r  # 旧版 0-5
    if isinstance(r, str) and r.startswith("TIER_"):
        try:
            return int(r.split("_")[1])
        except ValueError:
            return 0
    return 0


def _unwrap_m(value: Any, default: Any = None) -> Any:
    """解包游戏数据常见的 {m_defined, m_value} 包装。"""
    if isinstance(value, dict) and "m_value" in value:
        return value.get("m_value")
    if value is None:
        return default
    return value


def _attr_m(attr: dict, key: str) -> float:
    node = attr.get(key)
    unwrapped = _unwrap_m(node, 0)
    try:
        return float(unwrapped or 0)
    except (TypeError, ValueError):
        return 0.0


def _guess_damage_type(ed: dict) -> str:
    prefab = str(_unwrap_m(ed.get("prefabKey"), "") or "")
    apply = str(_unwrap_m(ed.get("applyWay"), "") or "")
    combined = f"{prefab} {apply}".upper()
    if "MAGIC" in combined:
        return "MAGIC"
    return "PHYS"


def _enemy_level_count(db: dict, enemy_id: str) -> int:
    for entry in db.get("enemies") or []:
        if entry.get("Key") == enemy_id:
            return len(entry.get("Value") or [])
    return 0


_store: GameDataStore | None = None
_store_lock = threading.Lock()


def memory_counts(store: GameDataStore | None = None) -> dict[str, int]:
    """使用 load 时缓存的计数，避免每次全表扫描。"""
    s = store or get_store()
    if s.counts:
        return dict(s.counts)
    return {
        "operators": len(s.list_operators(limit=99999)),
        "enemies": len(s.list_enemies(limit=99999)),
        "relics": len(s.relics),
    }


def get_store() -> GameDataStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = GameDataStore()
                _store.load()
                from app.data.db import db_counts, rebuild_from_store

                try:
                    counts = db_counts()
                    if counts.get("operators", 0) == 0:
                        rebuild_from_store(_store)
                except Exception as e:
                    logger.warning(f"MySQL 自动灌库跳过/失败: {e}")
    return _store


def reload_store() -> GameDataStore:
    """重载 JSON 并重建 MySQL；失败时抛出异常（禁止假成功）。"""
    global _store
    with _store_lock:
        _store = GameDataStore()
        _store.load()
        from app.data.db import rebuild_from_store

        rebuild_from_store(_store)
        return _store
