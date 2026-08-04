"""离线桌面版 FastAPI：只注册计算所需的只读接口。"""
from __future__ import annotations

import os
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import calc, enemies, operators, relics
from app.api.desktop import router as desktop_router
from app.data import db

SESSION_TOKEN = os.environ.get("ARKNIGHTS_SESSION_TOKEN") or secrets.token_urlsafe(32)
app = FastAPI(title="明日方舟离线面板", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def session_guard(request: Request, call_next):
    supplied = request.headers.get("X-Desktop-Token") or request.query_params.get("token")
    if request.url.path.startswith("/api/") and supplied != SESSION_TOKEN:
        return JSONResponse({"detail": "无效桌面会话"}, status_code=401)
    return await call_next(request)


app.include_router(operators.router, prefix="/api/v1/operators")
app.include_router(enemies.router, prefix="/api/v1/enemies")
app.include_router(relics.router, prefix="/api/v1/relics")
app.include_router(calc.router, prefix="/api/v1/calc")
app.include_router(desktop_router, prefix="/api/v1")


def mount_frontend(path: str) -> None:
    db.init_schema()
    app.mount("/", StaticFiles(directory=path, html=True), name="frontend")
