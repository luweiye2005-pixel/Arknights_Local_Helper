"""只读离线 JSON 数据层，接口与 mysql_db 的计算查询保持兼容。"""
from __future__ import annotations

import gzip
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings

SCHEMA_VERSION = 1


class OfflineDataError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    root = settings.offline_data_path
    manifest_path, payload_path = root / "manifest.json", root / "data.json.gz"
    if not manifest_path.exists() or not payload_path.exists():
        raise OfflineDataError(f"离线数据包缺失：{root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(manifest.get("schema_version") or 0) != SCHEMA_VERSION:
        raise OfflineDataError(f"不支持的数据版本：{manifest.get('schema_version')}")
    raw = payload_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest.get("data_sha256"):
        raise OfflineDataError("离线数据包校验失败")
    return json.loads(gzip.decompress(raw).decode("utf-8"))


def init_schema() -> None:
    _data()


def db_counts() -> dict[str, int]:
    d = _data()
    return {"operators": len(d["operators"]), "enemies": len(d["enemies"]), "relics": len(d["relics"]), "modules": sum(len(x.get("modules") or []) for x in d["operators"].values())}


def db_dsn_display() -> str: return "offline-json"
def source_name() -> str: return "json"
def db_path() -> Path: return settings.offline_data_path / "data.json.gz"
def get_meta(key: str, default: Any = None) -> Any: return _data().get("meta", {}).get(key, default)
def set_meta(key: str, value: Any) -> None: raise OfflineDataError("离线数据为只读")


def search_operators(q: str | None = None, limit: int = 50) -> list[dict]:
    q = (q or "").lower()
    rows = [x for x in _data()["operator_briefs"] if not q or q in x["name"].lower() or q in x["id"].lower() or q in str(x.get("profession_cn") or "").lower()]
    return rows[:limit]


def get_operator_detail(operator_id: str) -> dict | None: return _data()["operators"].get(operator_id)
def get_operator_skills(operator_id: str) -> list[dict]: return _data()["skills"].get(operator_id, [])


def search_enemies(q: str | None = None, limit: int = 50, theme_id: str | None = None) -> list[dict]:
    d, q = _data(), (q or "").lower()
    allowed = set(d["theme_enemies"].get(theme_id, [])) if theme_id else None
    rows = [x["brief"] for eid, x in d["enemies"].items() if (allowed is None or eid in allowed) and (not q or q in x["brief"]["name"].lower() or q in eid.lower())]
    return sorted(rows, key=lambda x: x["name"])[:limit]


def _enemy_targets(level: str | None) -> set[str]:
    return {"enemy"} | ({"elite_enemy"} if level == "ELITE" else {"boss"} if level == "BOSS" else set())


def get_enemy_row(enemy_id: str, level: int = 0, theme_id: str | None = None, equivalent_grade: int = 0) -> dict | None:
    row = _data()["enemies"].get(enemy_id)
    if not row: return None
    levels = row["levels"]
    lv = levels[min(max(level, 0), len(levels) - 1)] if levels else {}
    attrs = dict(lv.get("attributes") or {})
    applied, taken = [], {"phys": 0.0, "arts": 0.0}
    if theme_id:
        mul = {"hp": 0.0, "atk": 0.0, "def": 0.0}
        targets = _enemy_targets(row["brief"].get("enemy_level"))
        for mod in _data()["difficulty_mods"].get(theme_id, []):
            if int(mod["equivalent_grade"]) > equivalent_grade or mod["target"] not in targets: continue
            applied.append(mod); attr, value = mod["attr"], float(mod["value"])
            if attr in ("hp_pct", "atk_pct", "def_pct"): mul[attr[:-4]] += value
            elif attr == "damage_taken_phys_pct": taken["phys"] += value
            elif attr == "damage_taken_arts_pct": taken["arts"] += value
        for key in mul: attrs[key] = float(attrs.get(key) or 0) * (1 + mul[key])
    return {**row["brief"], "level_index": level, "attributes": attrs, "raw_level_count": len(levels), "difficulty_mods": applied, "damage_taken": taken}


def list_themes_db() -> list[dict]: return list(_data()["themes"])
def list_theme_difficulties(theme_id: str) -> list[dict]: return list(_data()["difficulties"].get(theme_id, []))


def get_relic_row(relic_id: str) -> dict | None: return _data()["relics"].get(relic_id)


def _steps_for(relic_id: str) -> list[dict]:
    groups = _data()["upgrade_groups"]
    for steps in groups.values():
        if any(x["relic_id"] == relic_id for x in steps): return steps
    return []


def resolve_relic_for_grade(relic_id: str, equivalent_grade: int, conn=None) -> dict | None:
    steps = [x for x in _steps_for(relic_id) if int(x["equivalent_grade_min"]) <= equivalent_grade]
    target = max(steps, key=lambda x: int(x["equivalent_grade_min"]))["relic_id"] if steps else relic_id
    return get_relic_row(target)


def get_relic_rule_rows(relic_ids: list[str], equivalent_grade: int = 0) -> list[dict]:
    out = []
    for rid in relic_ids:
        actual = (resolve_relic_for_grade(rid, equivalent_grade) or {"id": rid})["id"]
        out.extend(_data()["rules"].get(actual, []))
    return out


def get_relic_condition_schemas(theme_id: str | None = None) -> dict[str, dict]:
    schemas = _data()["conditions"]
    if not theme_id: return schemas
    return {rid: value for rid, value in schemas.items() if (_data()["relics"].get(rid) or {}).get("theme") == theme_id}


def get_theme_outer_buffs() -> dict[str, dict]: return _data()["outer_buffs"]


def search_relics(theme: str | None = None, q: str | None = None, limit: int = 500, equivalent_grade: int | None = None) -> list[dict]:
    d, q = _data(), (q or "").lower(); variants = {x["relic_id"] for steps in d["upgrade_groups"].values() for x in steps if int(x["equivalent_grade_min"]) > 0}
    out = []
    for rid, original in d["relics"].items():
        if rid in variants or (theme and original.get("theme") != theme): continue
        if q and q not in original["name"].lower() and q not in rid.lower() and q not in str(original.get("usage") or "").lower(): continue
        item = dict(original); actual = item
        if equivalent_grade is not None:
            actual = resolve_relic_for_grade(rid, equivalent_grade) or item
            if actual["id"] != rid: item.update({"resolved_id": actual["id"], "resolved_name": actual["name"], "name": actual["name"], "usage": actual.get("usage"), "icon_id": actual.get("icon_id")})
        item["icon_url"] = f"/api/v1/assets/relic/{actual['id']}"
        item["effects"] = [{k: r.get(k) for k in ("attr", "value", "target")} for r in d["rules"].get(actual["id"], []) if r.get("calculation_status") == "active"]
        out.append(item)
    return sorted(out, key=lambda x: (str(x.get("order_id") or ""), x["name"]))[:limit]


def get_relic_effects_merged(relic_ids: list[str], equivalent_grade: int = 0) -> list[dict]:
    out = []
    conditions = _data()["conditions"]
    for rid in relic_ids:
        candidates = sorted([x for x in _steps_for(rid) if int(x["equivalent_grade_min"]) <= equivalent_grade], key=lambda x: int(x["equivalent_grade_min"]), reverse=True) or [{"relic_id": rid}]
        for step in candidates:
            cid = step["relic_id"]
            rows = [r for r in _data()["rules"].get(cid, []) if r.get("calculation_status") == "active" and not r.get("when_param") and not r.get("value_expr") and cid not in conditions]
            if rows: out.extend(rows); break
    return out


def get_module(module_id: str) -> dict | None:
    for op in _data()["operators"].values():
        for module in op.get("modules") or []:
            if module["id"] == module_id: return module
    return None


def rebuild_from_store(store: Any) -> dict: raise OfflineDataError("离线数据为只读")
def refresh_theme_enemies(store: Any, download_missing: bool = True) -> dict: raise OfflineDataError("离线数据为只读")
