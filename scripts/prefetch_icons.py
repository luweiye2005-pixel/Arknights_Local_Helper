"""将藏品图标全部预下载到 data/icons/relics。

用法（仓库根目录，需先有 MySQL / 游戏数据）:
  backend\\.venv\\Scripts\\python scripts\\prefetch_icons.py
  backend\\.venv\\Scripts\\python scripts\\prefetch_icons.py --variants
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.data.store import reload_store  # noqa: E402
from app.services.local_assets import (  # noqa: E402
    copy_base_icons_for_variants,
    download_all_relic_icons,
    get_download_state,
)


def main() -> int:
    if "--variants" in sys.argv:
        print("复制基础图标到变种藏品…")
        result = copy_base_icons_for_variants()
        print(result)
        return 0 if result["skipped"] == 0 else 0
    print("重载游戏数据并确保 MySQL 就绪…")
    reload_store()
    print("开始下载藏品图标到本地…")
    state = download_all_relic_icons(workers=8)
    print(state.get("message"))
    # 下载完成后复制变种图标
    vr = copy_base_icons_for_variants()
    print(f"变种复制: {vr}")
    print(get_download_state().get("icons"))
    return 0 if state.get("fail", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
