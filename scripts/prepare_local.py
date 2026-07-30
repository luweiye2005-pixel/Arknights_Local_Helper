"""一键：同步游戏 JSON + 重建库 + 下载全部藏品图标到本地。

用法（仓库根目录）:
  backend\\.venv\\Scripts\\python scripts\\prepare_local.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def main() -> int:
    py = sys.executable
    print("==> 1/3 同步游戏 JSON")
    r = subprocess.run([py, str(ROOT / "scripts" / "sync_gamedata.py")], cwd=str(ROOT))
    if r.returncode != 0:
        print("游戏数据同步失败")
        return r.returncode

    print("==> 2/3 重建 MySQL")
    from app.data.store import reload_store
    from app.data import db as gdb

    reload_store()
    print("DB:", gdb.db_counts())

    print("==> 3/3 下载藏品图标到 data/icons/relics")
    from app.services.local_assets import download_all_relic_icons, get_download_state

    download_all_relic_icons(workers=8)
    print(get_download_state())
    print("完成。之后可离线使用本地 JSON / MySQL / 图标。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
