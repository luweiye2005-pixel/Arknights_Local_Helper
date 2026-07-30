"""敌人 API（MySQL）。"""
from fastapi import APIRouter, HTTPException, Query

from app.data import db as gdb

router = APIRouter()


@router.get("")
def list_enemies(
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    theme_id: str | None = Query(None),
):
    return {
        "items": gdb.search_enemies(q=q, limit=limit, theme_id=theme_id),
        "source": "mysql",
        "theme_id": theme_id,
    }


@router.get("/{enemy_id}")
def get_enemy(
    enemy_id: str,
    level: int = Query(0, ge=0),
    theme_id: str | None = Query(None),
    equivalent_grade: int = Query(0, ge=0),
):
    enemy = gdb.get_enemy_row(
        enemy_id,
        level=level,
        theme_id=theme_id,
        equivalent_grade=equivalent_grade,
    )
    if not enemy:
        raise HTTPException(404, f"未找到敌人 {enemy_id}")
    return enemy
