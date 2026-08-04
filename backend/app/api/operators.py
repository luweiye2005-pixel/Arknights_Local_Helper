"""干员 API（MySQL）。"""
from fastapi import APIRouter, HTTPException, Query

from app.data import db as gdb

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
    return {"items": gdb.search_operators(q=q, limit=limit), "source": gdb.source_name()}


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
    op = gdb.get_operator_detail(operator_id)
    if not op:
        raise HTTPException(404, f"未找到干员 {operator_id}")
    return {"operator_id": operator_id, "skills": gdb.get_operator_skills(operator_id), "source": gdb.source_name()}
