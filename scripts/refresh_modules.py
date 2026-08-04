"""从本地游戏数据仅刷新 MySQL 模组数据，不改动藏品规则。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.data.mysql_db import refresh_modules_from_store
from app.data.store import get_store


if __name__ == "__main__":
    print(refresh_modules_from_store(get_store()))
