"""敌人、主题敌人池与难度面板的 MySQL 查询。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import text

from app.data.mysql_core import get_engine, init_schema, set_meta

def search_enemies(
    q: str | None = None,
    limit: int = 50,
    theme_id: str | None = None,
) -> list[dict]:
    init_schema()
    params: dict[str, Any] = {"limit": limit}
    if theme_id:
        sql = """
            SELECT e.id, e.name, e.enemy_level, e.description
            FROM theme_enemies te
            JOIN enemies e ON e.id = te.enemy_id
            WHERE te.theme_id = :theme_id
        """
        params["theme_id"] = theme_id
        if q and q.strip():
            sql += " AND (e.name LIKE :like OR e.id LIKE :like)"
            params["like"] = f"%{q.strip()}%"
        sql += " ORDER BY e.name ASC LIMIT :limit"
    else:
        sql = "SELECT id,name,enemy_level,description FROM enemies"
        if q and q.strip():
            sql += " WHERE name LIKE :like OR id LIKE :like"
            params["like"] = f"%{q.strip()}%"
        sql += " ORDER BY name ASC LIMIT :limit"
    with get_engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]


def _enemy_diff_targets(enemy_level: str | None) -> set[str]:
    """难度修正目标：普通敌 + 对应精英/领袖。"""
    targets = {"enemy"}
    lv = (enemy_level or "").upper()
    if lv == "ELITE":
        targets.add("elite_enemy")
    elif lv == "BOSS":
        targets.add("boss")
    return targets


def get_enemy_row(enemy_id: str, level: int = 0, theme_id: str | None = None, equivalent_grade: int = 0) -> dict | None:
    init_schema()
    with get_engine().connect() as conn:
        en = conn.execute(text("SELECT * FROM enemies WHERE id=:id"), {"id": enemy_id}).mappings().first()
        if not en:
            return None
        lv = conn.execute(
            text(
                """
                SELECT * FROM enemy_levels
                WHERE enemy_id=:id AND level_index=:li
                """
            ),
            {"id": enemy_id, "li": level},
        ).mappings().first()
        if not lv:
            lv = conn.execute(
                text("SELECT * FROM enemy_levels WHERE enemy_id=:id ORDER BY level_index LIMIT 1"),
                {"id": enemy_id},
            ).mappings().first()
        max_lv = conn.execute(
            text("SELECT COUNT(*) FROM enemy_levels WHERE enemy_id=:id"),
            {"id": enemy_id},
        ).scalar() or 0

        attrs = {
            "hp": float((lv or {}).get("hp") or 0),
            "atk": float((lv or {}).get("atk") or 0),
            "def": float((lv or {}).get("def_stat") or 0),
            "magic_resistance": float((lv or {}).get("magic_resistance") or 0),
            "move_speed": float((lv or {}).get("move_speed") or 0),
            "attack_speed": float((lv or {}).get("attack_speed") or 0),
            "range_radius": float((lv or {}).get("range_radius") or 0),
            "damage_type": en["damage_type"],
        }
        applied_mods: list[dict] = []
        damage_taken = {"phys": 0.0, "arts": 0.0}
        if theme_id:
            mods = conn.execute(
                text(
                    """
                    SELECT target,attr,value,op,note FROM difficulty_stat_mods
                    WHERE theme_id=:tid AND equivalent_grade<=:eq
                    ORDER BY equivalent_grade
                    """
                ),
                {"tid": theme_id, "eq": equivalent_grade},
            ).mappings().all()
            targets = _enemy_diff_targets(en.get("enemy_level"))
            mul = {"hp": 0.0, "atk": 0.0, "def": 0.0}
            for m in mods:
                if m["target"] not in targets:
                    continue
                applied_mods.append(dict(m))
                attr = m["attr"]
                val = float(m["value"] or 0)
                if attr == "hp_pct":
                    mul["hp"] += val
                elif attr == "atk_pct":
                    mul["atk"] += val
                elif attr == "def_pct":
                    mul["def"] += val
                elif attr == "damage_taken_phys_pct":
                    damage_taken["phys"] += val
                elif attr == "damage_taken_arts_pct":
                    damage_taken["arts"] += val
            attrs["hp"] *= 1.0 + mul["hp"]
            attrs["atk"] *= 1.0 + mul["atk"]
            attrs["def"] *= 1.0 + mul["def"]

        return {
            "id": en["id"],
            "name": en["name"],
            "description": en["description"],
            "enemy_level": en["enemy_level"],
            "level_index": level,
            "attributes": attrs,
            "raw_level_count": int(max_lv),
            "difficulty_mods": applied_mods,
            "damage_taken": damage_taken,
        }


def refresh_theme_enemies(store: Any, *, download_missing: bool = True) -> dict[str, int]:
    """仅刷新主题敌人池（不重建其它表）。"""
    init_schema()
    from app.data.theme_enemy_sync import extract_theme_enemy_ids, iter_theme_details

    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE TABLE theme_enemies"))
        te_count = 0
        per_theme: dict[str, int] = {}
        for tid, detail in iter_theme_details(store.roguelike_topic_table):
            ids = extract_theme_enemy_ids(
                tid, detail, download_missing=download_missing, max_workers=8
            )
            n = 0
            for eid in ids:
                exists = conn.execute(
                    text("SELECT 1 FROM enemies WHERE id=:id"), {"id": eid}
                ).first()
                if not exists:
                    continue
                conn.execute(
                    text("INSERT IGNORE INTO theme_enemies(theme_id,enemy_id) VALUES(:tid,:eid)"),
                    {"tid": tid, "eid": eid},
                )
                n += 1
                te_count += 1
            per_theme[tid] = n
            logger.info(f"theme_enemies {tid}: {n}")
    set_meta("theme_enemies_refreshed_at", datetime.now(timezone.utc).isoformat())
    set_meta("theme_enemies_counts", per_theme)
    return {"theme_enemies": te_count, **{f"theme:{k}": v for k, v in per_theme.items()}}



