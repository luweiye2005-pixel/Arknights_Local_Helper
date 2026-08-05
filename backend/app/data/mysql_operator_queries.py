"""干员、技能与模组的 MySQL 查询。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.data.mysql_core import get_engine, init_schema

# ---------- queries ----------

def search_operators(q: str | None = None, limit: int = 50) -> list[dict]:
    init_schema()
    sql = """
        SELECT id,name,rarity,profession,profession_cn,sub_profession,position
        FROM operators
    """
    params: dict[str, Any] = {"limit": limit}
    if q and q.strip():
        sql += " WHERE name LIKE :like OR id LIKE :like OR appellation LIKE :like OR profession_cn LIKE :like"
        params["like"] = f"%{q.strip()}%"
    sql += " ORDER BY rarity DESC, name ASC LIMIT :limit"
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            pos = (d.get("position") or "").upper() or None
            d["position"] = pos
            d["position_cn"] = {"MELEE": "近战", "RANGED": "远程"}.get(pos or "", pos)
            out.append(d)
        return out


def get_operator_detail(operator_id: str) -> dict | None:
    init_schema()
    with get_engine().connect() as conn:
        op = conn.execute(text("SELECT * FROM operators WHERE id=:id"), {"id": operator_id}).mappings().first()
        if not op:
            return None
        phases_rows = conn.execute(
            text("SELECT elite,max_level,range_id FROM operator_phases WHERE operator_id=:id ORDER BY elite"),
            {"id": operator_id},
        ).mappings().all()
        phases = []
        raw_phases = []
        for ph in phases_rows:
            elite = int(ph["elite"])
            stats = conn.execute(
                text(
                    """
                    SELECT level,hp,atk,def_stat,res,aspd,base_attack_time
                    FROM operator_phase_stats
                    WHERE operator_id=:id AND elite=:elite ORDER BY level
                    """
                ),
                {"id": operator_id, "elite": elite},
            ).mappings().all()
            frames = [
                {
                    "level": int(s["level"]),
                    "data": {
                        "maxHp": float(s["hp"]),
                        "atk": float(s["atk"]),
                        "def": float(s["def_stat"]),
                        "magicResistance": float(s["res"]),
                        "attackSpeed": float(s["aspd"]),
                        "baseAttackTime": float(s["base_attack_time"]),
                    },
                }
                for s in stats
            ]
            phases.append({"elite": elite, "max_level": int(ph["max_level"]), "range_id": ph["range_id"]})
            raw_phases.append({"attributesKeyFrames": frames, "rangeId": ph["range_id"]})

        favor_rows = conn.execute(
            text("SELECT favor_level,hp,atk,def_stat FROM operator_favor_stats WHERE operator_id=:id ORDER BY favor_level"),
            {"id": operator_id},
        ).mappings().all()
        favor_key_frames = [
            {
                "level": int(f["favor_level"]),
                "data": {"maxHp": float(f["hp"]), "atk": float(f["atk"]), "def": float(f["def_stat"])},
            }
            for f in favor_rows
        ]

        mods = conn.execute(
            text("SELECT id,name,type_name,max_level,description FROM modules WHERE operator_id=:id"),
            {"id": operator_id},
        ).mappings().all()
        modules = []
        for m in mods:
            levels = conn.execute(
                text(
                    """
                    SELECT level,atk,atk_pct,hp,defense,attack_speed,trait_effects,talent_effects
                    FROM module_levels WHERE module_id=:mid ORDER BY level
                    """
                ),
                {"mid": m["id"]},
            ).mappings().all()
            modules.append(
                {
                    "id": m["id"],
                    "name": m["name"],
                    "type": m["type_name"],
                    "description": m["description"],
                    "max_level": int(m["max_level"] or 1),
                    "levels": [_module_level_dict(lv) for lv in levels],
                }
            )

        # talents
        talents_rows = conn.execute(
            text(
                """
                SELECT talent_index,unlock_elite,name,description,potential_rank,blackboard
                FROM operator_talents WHERE operator_id=:id
                ORDER BY talent_index, unlock_elite, potential_rank
                """
            ),
            {"id": operator_id},
        ).mappings().all()
        talents_out: list[dict] = []
        for t in talents_rows:
            bb = t["blackboard"]
            if isinstance(bb, str):
                try:
                    bb = json.loads(bb)
                except Exception:
                    bb = None
            talents_out.append({
                "index": int(t["talent_index"]),
                "unlock_elite": int(t.get("unlock_elite") or 0),
                "name": t["name"],
                "description": t["description"],
                "potential_rank": int(t["potential_rank"] or 0),
                "blackboard": bb,
            })

        pot_rows = conn.execute(
            text(
                """
                SELECT rank_index, attr, value FROM operator_potential_buffs
                WHERE operator_id=:id ORDER BY rank_index, attr
                """
            ),
            {"id": operator_id},
        ).mappings().all()
        pot_by_rank: dict[int, dict[str, float]] = {}
        for r in pot_rows:
            ri = int(r["rank_index"])
            pot_by_rank.setdefault(ri, {"hp": 0.0, "atk": 0.0, "def": 0.0, "aspd": 0.0, "res": 0.0})
            attr = str(r["attr"] or "")
            if attr in pot_by_rank[ri]:
                pot_by_rank[ri][attr] += float(r["value"] or 0)
        max_ri = max(pot_by_rank.keys(), default=-1)
        potential_ranks = [
            pot_by_rank.get(i, {"hp": 0.0, "atk": 0.0, "def": 0.0, "aspd": 0.0, "res": 0.0})
            for i in range(max_ri + 1)
        ]

        pos = (op.get("position") or "").upper() or None
        sub_id = op.get("sub_profession")
        sub_cn = None
        try:
            from app.data.store import get_store

            store = get_store()
            sub_cn = (
                (store.uni_equip_table.get("subProfDict") or {})
                .get(sub_id or "", {})
                .get("subProfessionName")
            )
            if not pos:
                raw = store.character_table.get(operator_id) or {}
                pos = (raw.get("position") or "").upper() or None
        except Exception:
            pass

        return {
            "id": op["id"],
            "name": op["name"],
            "rarity": int(op["rarity"] or 0),
            "profession": op["profession"],
            "profession_cn": op["profession_cn"],
            "sub_profession": sub_id,
            "sub_profession_cn": sub_cn,
            "position": pos,
            "position_cn": {"MELEE": "近战", "RANGED": "远程"}.get(pos or "", pos),
            "description": op["description"],
            "phases": phases,
            "skills": [],
            "talents": talents_out,
            "modules": modules,
            "favor_key_frames": favor_key_frames,
            "potential_ranks": potential_ranks,
            "raw_phases": raw_phases,
        }


def get_operator_skills(operator_id: str) -> list[dict]:
    """从 MySQL 返回前端自动填充所需的 Lv7 与最高技能等级。"""
    init_schema()
    with get_engine().connect() as conn:
        skills = conn.execute(
            text(
                """
                SELECT skill_id,skill_index,max_level
                FROM operator_skills
                WHERE operator_id=:operator_id
                ORDER BY skill_index
                """
            ),
            {"operator_id": operator_id},
        ).mappings().all()
        result: list[dict] = []
        for skill in skills:
            max_level = int(skill["max_level"] or 0)
            target_levels = [7] if max_level <= 7 else [7, max_level]
            rows = conn.execute(
                text(
                    """
                    SELECT level,name,description,duration,sp_cost,sp_init,parsed_effects
                    FROM operator_skill_levels
                    WHERE operator_id=:operator_id AND skill_id=:skill_id
                    ORDER BY level
                    """
                ),
                {
                    "operator_id": operator_id,
                    "skill_id": skill["skill_id"],
                },
            ).mappings().all()
            rows = [row for row in rows if int(row["level"]) in target_levels]
            levels_out = []
            for row in rows:
                parsed = row["parsed_effects"]
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
                parsed = parsed or {}
                levels_out.append(
                    {
                        "level": int(row["level"]),
                        "name": row["name"],
                        "description": row["description"],
                        "duration": float(row["duration"] or 0),
                        "sp_cost": row["sp_cost"],
                        "sp_init": row["sp_init"],
                        **parsed,
                    }
                )
            if levels_out:
                result.append(
                    {
                        "skill_id": skill["skill_id"],
                        "skill_name": levels_out[0].get("name"),
                        "max_level": max_level,
                        "levels": levels_out,
                    }
                )
        return result



def get_module(module_id: str) -> dict | None:
    init_schema()
    with get_engine().connect() as conn:
        m = conn.execute(text("SELECT * FROM modules WHERE id=:id"), {"id": module_id}).mappings().first()
        if not m:
            return None
        levels = conn.execute(
            text("SELECT level,atk,atk_pct,hp,defense,attack_speed,trait_effects,talent_effects FROM module_levels WHERE module_id=:id ORDER BY level"),
            {"id": module_id},
        ).mappings().all()
        return {
            "id": m["id"],
            "name": m["name"],
            "type": m["type_name"],
            "description": m["description"],
            "max_level": int(m["max_level"] or 1),
            "levels": [_module_level_dict(lv) for lv in levels],
        }


def _module_level_dict(row: Any) -> dict:
    result = dict(row)
    for field in ("trait_effects", "talent_effects"):
        value = result.get(field)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                value = []
        result[field] = value or []
    return result




