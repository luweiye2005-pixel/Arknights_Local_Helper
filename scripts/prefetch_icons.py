"""将藏品图标全部预下载到 data/icons/relics。

用法（仓库根目录，需先有 MySQL / 游戏数据）:
  backend\\.venv\\Scripts\\python scripts\\prefetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.data.store import reload_store  # noqa: E402
from app.services.local_assets import download_all_relic_icons, get_download_state  # noqa: E402


def main() -> int:
    print("重载游戏数据并确保 MySQL 就绪…")
    reload_store()
    print("开始下载藏品图标到本地…")
    state = download_all_relic_icons(workers=8)
    print(state.get("message"))
    print(get_download_state().get("icons"))
    return 0 if state.get("fail", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
