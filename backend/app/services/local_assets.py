"""本地资源下载与状态（藏品图标等）。"""
from __future__ import annotations

import html
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from app.config import settings
from app.data import db as gdb

# 优先 PRTS 镜像的官方藏品图（与游戏 iconId 一致）；失败再回退 Aceship
ICON_MIRRORS = [
    "https://torappu.prts.wiki/assets/roguelike_topic_itempic/{icon}.png",
    "https://cdn.jsdelivr.net/gh/Aceship/Arknight-Images@main/ui/roguelike/item/{icon}.png",
    "https://fastly.jsdelivr.net/gh/Aceship/Arknight-Images@main/ui/roguelike/item/{icon}.png",
    "https://raw.githubusercontent.com/Aceship/Arknight-Images/main/ui/roguelike/item/{icon}.png",
]

PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">'
    '<rect width="128" height="128" rx="12" fill="#1a2430"/>'
    '<text x="64" y="72" text-anchor="middle" fill="#6a7a88" font-size="13">{name}</text>'
    "</svg>"
)

ICON_FETCH_TIMEOUT = 20.0
ICON_FETCH_RETRIES = 2

_state_lock = threading.Lock()
_download_lock = threading.Lock()
_state: dict[str, Any] = {
    "running": False,
    "kind": None,
    "total": 0,
    "done": 0,
    "ok": 0,
    "fail": 0,
    "skipped": 0,
    "placeholder": 0,
    "message": "",
    "started_at": None,
    "finished_at": None,
}


def icons_root() -> Path:
    p = settings.icons_path / "relics"
    p.mkdir(parents=True, exist_ok=True)
    return p


def icon_png_path(relic_id: str) -> Path:
    return icons_root() / f"{relic_id}.png"


def icon_svg_path(relic_id: str) -> Path:
    return icons_root() / f"{relic_id}.svg"


def upgrade_base_relic_id(relic_id: str) -> str | None:
    """难度升级变体 *_a/_b/_c → 根藏品 id。"""
    m = re.match(r"^(.+)_[abc]$", relic_id or "")
    return m.group(1) if m else None


def icon_candidates(relic_id: str) -> list[str]:
    """按优先级返回可尝试的图标 id（自身 → 升级根）。"""
    out = [relic_id]
    base = upgrade_base_relic_id(relic_id)
    if base and base not in out:
        out.append(base)
    return out


def resolve_local_icon(relic_id: str) -> Path | None:
    """解析本地图标；升级变体缺图时回退到根藏品真图。"""
    for rid in icon_candidates(relic_id):
        png = icon_png_path(rid)
        if png.exists() and png.stat().st_size > 100:
            return png
    for rid in icon_candidates(relic_id):
        svg = icon_svg_path(rid)
        if svg.exists() and svg.stat().st_size > 20:
            return svg
    return None


def has_real_icon(relic_id: str) -> bool:
    for rid in icon_candidates(relic_id):
        png = icon_png_path(rid)
        if png.exists() and png.stat().st_size > 100:
            return True
    return False


def icon_status_path() -> Path:
    return settings.icons_path / "icons_meta.json"


def icons_revision() -> int:
    """本地图标目录最近修改时间，供前端缓存破除。"""
    root = icons_root()
    latest = 0
    try:
        for p in root.iterdir():
            if p.is_file() and p.suffix.lower() in {".png", ".svg"}:
                latest = max(latest, int(p.stat().st_mtime))
    except OSError:
        pass
    return latest


def count_local_icons() -> dict[str, int]:
    root = icons_root()
    png_ids = {p.stem for p in root.glob("*.png") if p.is_file() and p.stat().st_size > 100}
    svg_ids = {
        p.stem
        for p in root.glob("*.svg")
        if p.is_file() and p.stat().st_size > 20 and p.stem not in png_ids
    }
    ids = png_ids | svg_ids
    relic_total = gdb.db_counts().get("relics", 0)
    return {
        "cached": len(ids),
        "png": len(png_ids),
        "placeholder": len(svg_ids),
        "relics_in_db": relic_total,
        "missing": max(0, relic_total - len(ids)),
        "revision": icons_revision(),
    }


def get_download_state() -> dict[str, Any]:
    with _state_lock:
        st = dict(_state)
    st["icons"] = count_local_icons()
    return st


def _set_state(**kwargs: Any) -> None:
    with _state_lock:
        _state.update(kwargs)


def _write_placeholder(relic_id: str, name: str = "Relic") -> None:
    label = html.escape((name or "Relic")[:8])
    svg = PLACEHOLDER_SVG.replace("{name}", label)
    icon_svg_path(relic_id).write_text(svg, encoding="utf-8")


def fetch_one_icon(
    relic_id: str,
    icon_id: str | None = None,
    name: str = "Relic",
    timeout: float = ICON_FETCH_TIMEOUT,
    client: httpx.Client | None = None,
) -> str:
    """
    下载单个图标到本地。
    返回: ok | skipped | placeholder
    已有真图(png)则跳过；仅有占位(svg)时会再尝试拉取真图。
    """
    png = icon_png_path(relic_id)
    if has_real_icon(relic_id):
        return "skipped"

    icon = icon_id or relic_id
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=timeout, follow_redirects=True)
    assert client is not None

    try:
        # 变体优先下自己的 icon；失败再试根藏品 icon，并复制到变体路径
        try_icons = []
        for cand in [icon, *icon_candidates(relic_id)]:
            if cand and cand not in try_icons:
                try_icons.append(cand)

        for try_icon in try_icons:
            for tmpl in ICON_MIRRORS:
                url = tmpl.format(icon=try_icon)
                for attempt in range(ICON_FETCH_RETRIES):
                    try:
                        resp = client.get(url)
                        if resp.status_code == 200 and len(resp.content) > 500:
                            png.write_bytes(resp.content)
                            svg = icon_svg_path(relic_id)
                            if svg.exists():
                                try:
                                    svg.unlink()
                                except OSError:
                                    pass
                            return "ok"
                        if resp.status_code == 404:
                            break
                    except Exception as e:
                        logger.debug(f"icon try fail {url} ({attempt + 1}): {e}")
                        if attempt + 1 < ICON_FETCH_RETRIES:
                            time.sleep(0.3 * (attempt + 1))

        # CDN 无变体图时，直接复用本地根藏品 png
        base = upgrade_base_relic_id(relic_id)
        if base:
            base_png = icon_png_path(base)
            if base_png.exists() and base_png.stat().st_size > 100:
                png.write_bytes(base_png.read_bytes())
                svg = icon_svg_path(relic_id)
                if svg.exists():
                    try:
                        svg.unlink()
                    except OSError:
                        pass
                return "ok"
    finally:
        if own_client:
            client.close()

    # 拉取失败也落盘占位图，保证「本地有文件」
    _write_placeholder(relic_id, name=name)
    return "placeholder"


def _persist_meta() -> None:
    meta = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "icons": count_local_icons(),
        "last_job": {k: v for k, v in get_download_state().items() if k != "icons"},
    }
    icon_status_path().parent.mkdir(parents=True, exist_ok=True)
    icon_status_path().write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def download_all_relic_icons(
    theme: str | None = None,
    workers: int = 6,
    force: bool = False,
    only_missing: bool = True,
) -> dict[str, Any]:
    """同步下载全部（或指定主题）藏品图标到本地。默认会补下占位图/缺失项。"""
    if not _download_lock.acquire(blocking=False):
        return {**get_download_state(), "message": "已有下载任务在进行"}

    try:
        items = gdb.search_relics(theme=theme, limit=5000)
        if force:
            for it in items:
                for p in (icon_png_path(it["id"]), icon_svg_path(it["id"])):
                    if p.exists():
                        try:
                            p.unlink()
                        except OSError:
                            pass

        if only_missing and not force:
            pending = [it for it in items if not has_real_icon(it["id"])]
            skipped_preset = len(items) - len(pending)
            items = pending
        else:
            skipped_preset = 0

        total = len(items)
        _set_state(
            running=True,
            kind="relic_icons",
            total=total,
            done=0,
            ok=0,
            fail=0,
            skipped=skipped_preset,
            placeholder=0,
            message=f"开始补全 {total} 个藏品图标（已有真图跳过 {skipped_preset}）…",
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None,
        )

        if total == 0:
            _set_state(
                running=False,
                message=f"无需下载：真图已齐全（跳过 {skipped_preset}）",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            _persist_meta()
            return get_download_state()

        ok = skipped = placeholder = 0
        done = 0
        thread_local = threading.local()

        def get_client() -> httpx.Client:
            cli = getattr(thread_local, "client", None)
            if cli is None:
                cli = httpx.Client(
                    timeout=ICON_FETCH_TIMEOUT,
                    follow_redirects=True,
                    headers={"User-Agent": "ArknightsLocalHelper/0.1 (local; relic-icons)"},
                )
                thread_local.client = cli
            return cli

        def work(it: dict) -> str:
            return fetch_one_icon(
                it["id"],
                icon_id=it.get("icon_id"),
                name=it.get("name") or "Relic",
                client=get_client(),
            )

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {pool.submit(work, it): it for it in items}
            for fut in as_completed(futures):
                result = fut.result()
                done += 1
                if result == "ok":
                    ok += 1
                elif result == "skipped":
                    skipped += 1
                else:
                    placeholder += 1
                _set_state(
                    done=done,
                    ok=ok,
                    fail=0,
                    skipped=skipped_preset + skipped,
                    placeholder=placeholder,
                    message=f"本地图标进度 {done}/{total}（新下真图 {ok} / 仍占位 {placeholder}）",
                )

        _set_state(
            running=False,
            done=done,
            ok=ok,
            fail=0,
            skipped=skipped_preset + skipped,
            placeholder=placeholder,
            message=(
                f"完成：新下真图 {ok}，已有跳过 {skipped_preset + skipped}，"
                f"仍占位 {placeholder}"
            ),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        _persist_meta()
        return get_download_state()
    except Exception as e:
        _set_state(running=False, message=f"下载失败: {e}", finished_at=datetime.now(timezone.utc).isoformat())
        raise
    finally:
        _download_lock.release()


def copy_base_icons_for_variants() -> dict[str, int]:
    """为缺失图标的变种藏品复制其基础版本的图标。"""
    import shutil
    from app.data import db as _gdb

    root = icons_root()
    all_relics = _gdb.search_relics(limit=5000)
    copied = 0
    skipped = 0

    png_icons: set[str] = {
        p.stem for p in root.glob("*.png")
        if p.is_file() and p.stat().st_size > 100
    }

    def _copy(src_stem: str, dst_stem: str) -> bool:
        for suffix in (".png", ".webp", ".jpg"):
            src = root / f"{src_stem}{suffix}"
            if src.is_file():
                dst = root / f"{dst_stem}{suffix}"
                if not dst.exists():
                    shutil.copy2(src, dst)
                return True
        return False

    for relic in all_relics:
        rid = relic.get("id", "")
        icon_id = relic.get("icon_id") or rid
        if icon_id in png_icons:
            continue

        # 策略1: 去掉 _a / _b / _c 后缀
        base = re.sub(r"_[abc]$", "", icon_id)
        if base != icon_id and base in png_icons:
            if _copy(base, icon_id):
                png_icons.add(icon_id)
                copied += 1
            continue

        # 策略2: relic.id 去掉 _a/_b/_c 后缀后查找
        base_rid = re.sub(r"_[abc]$", "", rid)
        if base_rid != rid:
            for cand in {relic.get("icon_id") or base_rid, base_rid}:
                if cand in png_icons:
                    if _copy(cand, icon_id):
                        png_icons.add(icon_id)
                        copied += 1
                    break
            else:
                skipped += 1
        else:
            skipped += 1

    logger.info(f"变种图标复制: {copied} done, {skipped} skipped")
    _persist_meta()
    return {"copied": copied, "skipped": skipped}


def start_download_all_relic_icons_async(theme: str | None = None, workers: int = 6) -> dict[str, Any]:
    """后台线程启动全量图标下载（含占位图补全）。"""
    if _state.get("running"):
        return get_download_state()

    # 先标记 running，避免接口立刻返回「未开始」造成误解
    _set_state(
        running=True,
        kind="relic_icons",
        message="正在准备补全藏品图标…",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
    )

    def runner() -> None:
        try:
            download_all_relic_icons(theme=theme, workers=workers, only_missing=True)
        except Exception as e:
            logger.error(f"async icon download failed: {e}")
            _set_state(
                running=False,
                message=f"下载失败: {e}",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

    threading.Thread(target=runner, name="relic-icon-download", daemon=True).start()
    time.sleep(0.1)
    return get_download_state()


# 兼容旧名
def icon_path(relic_id: str) -> Path:
    return icon_png_path(relic_id)
