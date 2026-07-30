"""本地资源：藏品图标只读本地；下载走独立接口。"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, Response

from app.services import local_assets as la

router = APIRouter()

FALLBACK_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">'
    b'<rect width="128" height="128" fill="#1a2430"/>'
    b'<text x="64" y="70" text-anchor="middle" fill="#6a7a88" font-size="14">Relic</text>'
    b"</svg>"
)


@router.get("/status")
def assets_status():
    return la.get_download_state()


@router.get("/relic/{relic_id}")
def relic_icon(relic_id: str):
    """只读本地缓存（png 真图或 svg 占位）；绝不访问外网。"""
    path = la.resolve_local_icon(relic_id)
    if path is not None:
        is_png = path.suffix.lower() == ".png"
        media = "image/png" if is_png else "image/svg+xml"
        # 真图可长缓存；占位图短缓存，便于补全后立刻看到新图
        cache = "public, max-age=604800" if is_png else "public, max-age=30, must-revalidate"
        return FileResponse(
            path,
            media_type=media,
            headers={
                "Cache-Control": cache,
                "ETag": f'"{path.stat().st_mtime_ns}-{path.stat().st_size}"',
            },
        )
    return Response(
        content=FALLBACK_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/relics/prefetch")
def prefetch_relic_icons(
    theme: str | None = None,
    all: bool = Query(True, description="是否下载全部藏品图标"),
    background: bool = Query(True, description="后台下载，不阻塞请求"),
):
    """
    将藏品图标预先保存到 data/icons/relics/。
    会自动重试仅有占位图的条目；能下到真图则存 png。
    """
    if background:
        state = la.start_download_all_relic_icons_async(theme=None if all else theme)
        return {"mode": "background", **state}
    state = la.download_all_relic_icons(theme=None if all else theme, only_missing=True)
    return {"mode": "sync", **state}
