"""Probe theme enemy pools and difficulty mods."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT / "backend"))

from app.data.mysql_db import get_engine  # noqa: E402
from app.data.store import get_store  # noqa: E402


def main() -> None:
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(
            text("SELECT enemy_level, COUNT(*) c FROM enemies GROUP BY enemy_level")
        ).fetchall()
        print("enemy_levels", rows)
        rows = c.execute(
            text(
                "SELECT target, attr, COUNT(*) c FROM difficulty_stat_mods "
                "GROUP BY target, attr ORDER BY c DESC"
            )
        ).fetchall()
        print("diff_mods", rows)
        rows = c.execute(
            text(
                "SELECT target, attr, COUNT(*) c FROM relic_effects "
                "GROUP BY target, attr ORDER BY c DESC LIMIT 20"
            )
        ).fetchall()
        print("relic_effects", rows)

    store = get_store()
    details = store.roguelike_topic_table.get("details") or {}
    for tid, detail in list(details.items())[:2]:
        if not isinstance(detail, dict):
            continue
        stages = detail.get("stages") or {}
        print(f"\ntheme {tid} stages={len(stages)}")
        # sample stage keys
        for i, (sid, st) in enumerate(stages.items()):
            if i >= 3:
                break
            print("  stage", sid, "levelId=", (st or {}).get("levelId"), "keys", list((st or {}).keys())[:8])
        gc = detail.get("gameConst") or {}
        print("  bossIds", len(gc.get("bossIds") or []), "mimic", len(gc.get("mimicEnemyIds") or []))


if __name__ == "__main__":
    main()
