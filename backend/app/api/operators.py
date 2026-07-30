"""干员 API（MySQL）。"""
from fastapi import APIRouter, HTTPException, Query

from app.combat.attributes import skill_multiplier_and_duration
from app.data import db as gdb
from app.data.store import get_store

router = APIRouter()


def _slim_operator(op: dict) -> dict:
    out = dict(op)
    out.pop("favor_key_frames", None)
    out.pop("potential_ranks", None)
    # 保留 raw_phases 供前端不需要，但面板服务端自算；前端只要 phases
    # skills 当前未入库，返回空列表
    out["skills"] = out.get("skills") or []
    return out


@router.get("")
def list_operators(q: str | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    return {"items": gdb.search_operators(q=q, limit=limit), "source": "mysql"}


@router.get("/{operator_id}")
def get_operator(operator_id: str):
    op = gdb.get_operator_detail(operator_id)
    if not op:
        raise HTTPException(404, f"未找到干员 {operator_id}")
    return _slim_operator(op)


@router.get("/{operator_id}/skills")
def get_operator_skills(operator_id: str):
    """返回干员所有技能的倍率参数，供前端自动填充。

    只返回 Lv7（满级）和 Lv10（专三），以简化前端选择。
    3星干员技能最高7级无专精，1-2星无技能。
    """
    store = get_store()
    op = store.get_operator(operator_id)
    if not op:
        raise HTTPException(404, f"未找到干员 {operator_id}")

    skills_out = []
    for skill in op.get("skills") or []:
        skill_id = skill.get("skill_id")
        all_levels = skill.get("levels") or []
        max_lv = len(all_levels)
        if max_lv == 0:
            continue

        # 只取 Lv7 和最高级（通常 Lv10=专三，3星 Lv7=满级）
        target_levels = [7] if max_lv == 7 else [7, max_lv]
        levels_out = []
        for lvl in target_levels:
            info = skill_multiplier_and_duration(all_levels, lvl)
            levels_out.append({
                "level": lvl,
                "name": info["name"],
                "atk_scale": info["atk_scale"],
                "duration": info["duration"],
                "description": info["description"],
                "sp_cost": (all_levels[lvl - 1].get("sp_data") or {}).get("spCost") if lvl <= len(all_levels) else None,
                "sp_init": (all_levels[lvl - 1].get("sp_data") or {}).get("initSp") if lvl <= len(all_levels) else None,
                "attack_speed": info["attack_speed"],
                "base_attack_time": info["base_attack_time"],
                "damage_scale": info["damage_scale"],
                "secondary_scale": info["secondary_scale"],
                "cnt": info["cnt"],
                "hp_pct": info["hp_pct"],
                "def_pct": info["def_pct"],
            })
        skills_out.append({
            "skill_id": skill_id,
            "skill_name": levels_out[0].get("name"),
            "max_level": max_lv,
            "levels": levels_out,
        })

    return {"operator_id": operator_id, "skills": skills_out}
