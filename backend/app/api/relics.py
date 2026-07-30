"""遗物 API（MySQL）。"""
from fastapi import APIRouter, HTTPException, Query

from app.combat.relics import get_outer_buff, list_condition_schemas, load_outer_buffs
from app.data import db as gdb

router = APIRouter()


@router.get("/themes")
def list_themes():
    return {"themes": gdb.list_themes_db(), "source": "mysql"}


@router.get("/themes/{theme_id}/difficulties")
def list_difficulties(theme_id: str):
    items = gdb.list_theme_difficulties(theme_id)
    return {"theme_id": theme_id, "items": items, "source": "mysql"}


@router.get("/themes/{theme_id}/outer-buff")
def theme_outer_buff(theme_id: str):
    buff = get_outer_buff(theme_id) or {
        "name": theme_id,
        "atk_pct": 0,
        "hp_pct": 0,
        "def_pct": 0,
        "aspd": 0,
        "note": "未配置满级局外数值",
    }
    return {"theme_id": theme_id, "buff": buff}


@router.get("/conditions")
def relic_conditions(theme: str | None = Query(None)):
    schemas = list_condition_schemas(theme)
    return {"theme": theme, "items": schemas, "count": len(schemas)}


@router.get("/outer-buffs")
def outer_buffs():
    return {"items": load_outer_buffs()}


@router.get("")
def list_relics(
    theme: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(2000, ge=1, le=5000),
    equivalent_grade: int | None = Query(None, ge=0),
):
    items = gdb.search_relics(theme=theme, q=q, limit=limit, equivalent_grade=equivalent_grade)
    schemas = list_condition_schemas(theme)
    for it in items:
        schema = schemas.get(it["id"])
        if schema:
            it["condition_schema"] = {
                "params": schema.get("params") or [],
                "name": schema.get("name"),
            }
    return {
        "themes": gdb.list_themes_db(),
        "items": items,
        "conditions": schemas,
        "source": "mysql",
    }


@router.get("/{relic_id}")
def get_relic(relic_id: str, equivalent_grade: int = Query(0, ge=0)):
    r = gdb.resolve_relic_for_grade(relic_id, equivalent_grade) or gdb.get_relic_row(relic_id)
    if not r:
        raise HTTPException(404, f"未找到遗物 {relic_id}")
    detail = gdb.get_relic_row(r["id"]) or r
    detail = dict(detail)
    detail["base_id"] = relic_id
    detail["icon_url"] = f"/api/v1/assets/relic/{detail['id']}"
    schemas = list_condition_schemas()
    if relic_id in schemas:
        detail["condition_schema"] = schemas[relic_id]
    elif detail.get("id") in schemas:
        detail["condition_schema"] = schemas[detail["id"]]
    return detail
