"""从 ArknightsGameData 同步游戏 JSON 到 data/gamedata。

优先国内可访问镜像，失败再回落 raw.githubusercontent.com。
用法（在仓库根目录）:
  python scripts/sync_gamedata.py
  python scripts/sync_gamedata.py --levels   # 额外同步集成战略关卡（主题敌人池）
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "gamedata"
sys.path.insert(0, str(ROOT / "backend"))

FILES = {
    "character_table.json": "zh_CN/gamedata/excel/character_table.json",
    "skill_table.json": "zh_CN/gamedata/excel/skill_table.json",
    "uniequip_table.json": "zh_CN/gamedata/excel/uniequip_table.json",
    "battle_equip_table.json": "zh_CN/gamedata/excel/battle_equip_table.json",
    "enemy_handbook_table.json": "zh_CN/gamedata/excel/enemy_handbook_table.json",
    "roguelike_topic_table.json": "zh_CN/gamedata/excel/roguelike_topic_table.json",
    "enemy_database.json": "zh_CN/gamedata/levels/enemydata/enemy_database.json",
}

MIRRORS = [
    "https://cdn.jsdelivr.net/gh/Kengxxiao/ArknightsGameData@master/{path}",
    "https://raw.gitmirror.com/Kengxxiao/ArknightsGameData/master/{path}",
    "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/{path}",
]


def download(path: str) -> bytes:
    last_err = None
    for tmpl in MIRRORS:
        url = tmpl.format(path=path)
        try:
            print(f"  GET {url}")
            with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()
                return r.content
        except Exception as e:
            print(f"  fail: {e}")
            last_err = e
    raise RuntimeError(f"全部镜像失败: {path} ({last_err})")


def sync_levels() -> dict:
    from app.data.theme_enemy_sync import sync_all_theme_levels

    topic_path = OUT / "roguelike_topic_table.json"
    if not topic_path.exists():
        raise FileNotFoundError("缺少 roguelike_topic_table.json，请先同步主表")
    table = json.loads(topic_path.read_text(encoding="utf-8"))
    print("同步集成战略关卡 JSON ...")
    return sync_all_theme_levels(table, max_workers=10)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", action="store_true", help="同步 Roguelike 关卡 JSON")
    parser.add_argument("--levels-only", action="store_true", help="只同步关卡，跳过主表")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    total = 0
    if not args.levels_only:
        total = len(FILES)
        for name, rel in FILES.items():
            print(f"同步 {name} ...")
            try:
                data = download(rel)
                dest = OUT / name
                dest.write_bytes(data)
                json.loads(data)
                print(f"  -> {dest} ({len(data)} bytes)")
                ok += 1
            except Exception as e:
                print(f"  ERROR: {e}")
    else:
        ok = total = 1

    level_stats = None
    if args.levels or args.levels_only:
        try:
            level_stats = sync_levels()
            print(f"  levels -> {level_stats}")
        except Exception as e:
            print(f"  levels ERROR: {e}")
            return 1

    meta = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "source": "Kengxxiao/ArknightsGameData",
        "files_ok": ok,
        "files_total": total,
        "levels": level_stats,
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成 {ok}/{total}，meta 已写入")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
