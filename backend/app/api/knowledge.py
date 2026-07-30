"""数据管理 API：同步 JSON、入库 MySQL、一键本地化。"""
from __future__ import annotations

import subprocess
import sys

from fastapi import APIRouter, HTTPException, Query

from app.config import REPO_ROOT, settings
from app.data import db as gdb
from app.data.store import get_store, memory_counts, reload_store
from app.services import local_assets as la

router = APIRouter()


@router.get("/status")
def data_status():
    store = get_store()
    gdir = settings.gamedata_path
    files = {
        name: (gdir / name).exists()
        for name in [
            "character_table.json",
            "enemy_handbook_table.json",
            "enemy_database.json",
            "skill_table.json",
            "uniequip_table.json",
            "battle_equip_table.json",
            "roguelike_topic_table.json",
            "meta.json",
        ]
    }
    mem = memory_counts(store)
    try:
        db_c = gdb.db_counts()
        db_ok = True
        db_err = None
    except Exception as e:
        db_c = {}
        db_ok = False
        db_err = str(e)
    icons = la.count_local_icons()
    return {
        "gamedata_dir": str(gdir),
        "mysql_dsn": gdb.db_dsn_display(),
        "mysql_ok": db_ok,
        "mysql_error": db_err,
        "icons_dir": str(la.icons_root()),
        "files": files,
        "meta": store.meta,
        "db_meta": {
            "rebuilt_at": gdb.get_meta("rebuilt_at") if db_ok else None,
            "counts": gdb.get_meta("counts") if db_ok else None,
        },
        "memory_counts": mem,
        "db_counts": db_c,
        "counts": db_c,
        "icons": icons,
        "download": la.get_download_state(),
        "in_sync": bool(
            db_ok
            and mem.get("operators") == db_c.get("operators")
            and mem.get("enemies") == db_c.get("enemies")
            and mem.get("relics") == db_c.get("relics")
        ),
        "local_ready": bool(
            db_c.get("operators", 0) > 50
            and icons.get("cached", 0) >= max(1, int(icons.get("relics_in_db", 0) * 0.8))
        ),
    }


def _reload_with_counts() -> dict:
    try:
        store = reload_store()
    except Exception as e:
        raise HTTPException(
            500,
            f"MySQL 重建失败: {e}\n内存计数={memory_counts()}",
        ) from e
    mem = memory_counts(store)
    db_c = gdb.db_counts()
    return {
        "ok": True,
        "memory_counts": mem,
        "db_counts": db_c,
        "counts": db_c,
        "meta": store.meta,
        "icons": la.count_local_icons(),
    }


@router.post("/reload-gamedata")
def reload_gamedata():
    return _reload_with_counts()


@router.post("/sync-gamedata")
def sync_gamedata():
    """拉取游戏 JSON 并重建 MySQL。"""
    script = REPO_ROOT / "scripts" / "sync_gamedata.py"
    if not script.exists():
        raise HTTPException(404, f"找不到同步脚本: {script}")
    py = sys.executable
    proc = subprocess.run(
        [py, str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    if proc.returncode != 0:
        raise HTTPException(
            500,
            f"同步失败 (code={proc.returncode})\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}",
        )
    result = _reload_with_counts()
    result["log"] = (proc.stdout or "")[-3000:]
    return result


@router.post("/rebuild-db")
def rebuild_db():
    try:
        counts = gdb.rebuild_from_store(get_store())
    except Exception as e:
        raise HTTPException(500, f"重建失败: {e}") from e
    return {
        "ok": True,
        "counts": counts,
        "memory_counts": memory_counts(),
        "db_counts": gdb.db_counts(),
        "icons": la.count_local_icons(),
    }


@router.post("/refresh-theme-enemies")
def refresh_theme_enemies(download_missing: bool = Query(True)):
    """同步/解析关卡敌人池并写入 theme_enemies（无需全量重建）。"""
    script = REPO_ROOT / "scripts" / "sync_gamedata.py"
    if download_missing and script.exists():
        proc = subprocess.run(
            [sys.executable, str(script), "--levels-only"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1200,
        )
        if proc.returncode != 0:
            raise HTTPException(
                500,
                f"关卡同步失败 (code={proc.returncode})\n{(proc.stdout or '')[-1500:]}\n{(proc.stderr or '')[-1500:]}",
            )
    try:
        counts = gdb.refresh_theme_enemies(get_store(), download_missing=download_missing)
    except Exception as e:
        raise HTTPException(500, f"刷新主题敌人失败: {e}") from e
    return {"ok": True, "counts": counts, "db_counts": gdb.db_counts()}


@router.post("/prepare-local")
def prepare_local(
    download_icons: bool = Query(True, description="同步数据后是否后台下载全部藏品图标"),
):
    """
    一键本地化：
    1) 拉取游戏 JSON 到 data/gamedata
    2) 重建 MySQL
    3) 后台下载全部藏品图标到 data/icons/relics
    """
    gdir = settings.gamedata_path
    need_sync = not (gdir / "character_table.json").exists() or (
        (gdir / "character_table.json").stat().st_size < 1_000_000
    )
    if need_sync:
        sync_result = sync_gamedata()
    else:
        sync_result = _reload_with_counts()

    icon_job = None
    if download_icons:
        icon_job = la.start_download_all_relic_icons_async()

    return {
        "ok": True,
        "synced": need_sync,
        "data": sync_result,
        "icons_job": icon_job,
        "message": "数据已写入 MySQL；图标正在后台下载到本地，可刷新查看进度",
    }
