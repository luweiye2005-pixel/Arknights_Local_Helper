# -*- coding: utf-8 -*-
"""用本地已有关卡刷新 theme_enemies（不下载缺失文件）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.data.mysql_db import init_schema, refresh_theme_enemies, db_counts  # noqa: E402
from app.data.store import get_store  # noqa: E402


def main() -> None:
    init_schema()
    store = get_store()
    counts = refresh_theme_enemies(store, download_missing=False)
    print("refresh:", counts)
    print("db:", db_counts())


if __name__ == "__main__":
    main()
