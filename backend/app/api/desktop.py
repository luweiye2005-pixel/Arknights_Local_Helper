"""桌面版仅有的本地资源与用户配置接口。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.config import settings
from app.data import db as gdb

router = APIRouter()
FALLBACK = b'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect width="128" height="128" fill="#1a2430"/></svg>'


def _state_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ArknightsOfflinePanel"
    return root / "panel_state.json"


@router.get("/knowledge/panel-state")
def load_state():
    path = _state_path()
    if not path.exists(): return {"version": 1}
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {"version": 1}


@router.post("/knowledge/panel-state")
def save_state(body: dict):
    if len(json.dumps(body, ensure_ascii=False)) > 1_000_000: raise HTTPException(413, "配置过大")
    body = {**body, "version": 1}; path = _state_path(); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": True, "version": 1}


@router.get("/assets/relic/{relic_id}")
def relic_icon(relic_id: str):
    row = gdb.get_relic_row(relic_id) or {}
    for candidate in (row.get("icon_id"), relic_id):
        safe = "".join(ch for ch in str(candidate or "") if ch.isalnum() or ch in "_-")
        for suffix in (".png", ".webp", ".jpg"):
            path = settings.icons_path / "relics" / f"{safe}{suffix}"
            if path.is_file(): return FileResponse(path, headers={"Cache-Control": "public,max-age=604800"})
    return Response(FALLBACK, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
