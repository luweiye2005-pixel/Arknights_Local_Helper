"""API 路由聚合（精简版）。"""
from fastapi import APIRouter

from app.api import assets, calc, enemies, knowledge, operators, relics

api_router = APIRouter()
api_router.include_router(operators.router, prefix="/operators", tags=["operators"])
api_router.include_router(enemies.router, prefix="/enemies", tags=["enemies"])
api_router.include_router(relics.router, prefix="/relics", tags=["relics"])
api_router.include_router(calc.router, prefix="/calc", tags=["calc"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
