"""FastAPI 入口：明日方舟本地数据面板。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api import api_router
from app.config import settings
from app.data.store import get_store, memory_counts


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Arknights Local Panel...")
    store = get_store()
    logger.info(f"Memory counts: {memory_counts(store)}")
    yield
    logger.info("Shutdown complete")


app = FastAPI(
    title="明日方舟本地数据面板",
    description="同步游戏数据到 SQLite，查看属性，计算藏品加成后面板",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {"name": "明日方舟本地数据面板", "version": "0.2.0", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}
