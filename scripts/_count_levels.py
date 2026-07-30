"""Count unique Roguelike level files across themes."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.data.store import get_store  # noqa: E402


def level_id_to_path(level_id: str) -> str | None:
    # Obt/Roguelike/RO1/level_rogue1_1-1 -> zh_CN/gamedata/levels/obt/roguelike/ro1/level_rogue1_1-1.json
    if not level_id:
        return None
    parts = level_id.replace("\\", "/").split("/")
    if len(parts) < 2:
        return None
    fname = parts[-1]
    # RO1 -> ro1
    folder = None
    for p in parts:
        if p.upper().startswith("RO") and p[2:].isdigit():
            folder = p.lower()
            break
    if not folder:
        # try from filename level_rogue1_
        import re
        m = re.search(r"level_rogue(\d+)", fname, re.I)
        if m:
            folder = f"ro{m.group(1)}"
    if not folder:
        return None
    return f"zh_CN/gamedata/levels/obt/roguelike/{folder}/{fname}.json"


def main() -> None:
    store = get_store()
    details = store.roguelike_topic_table.get("details") or {}
    all_levels: set[str] = set()
    per_theme: dict[str, set[str]] = {}
    for tid, detail in details.items():
        if not isinstance(detail, dict):
            continue
        ids: set[str] = set()
        for st in (detail.get("stages") or {}).values():
            lid = (st or {}).get("levelId")
            if lid:
                ids.add(lid)
            for r in (st or {}).get("levelReplaceIds") or []:
                if r:
                    ids.add(r)
        per_theme[tid] = ids
        all_levels |= ids
        print(tid, "stages", len(detail.get("stages") or {}), "unique_levels", len(ids))
    print("TOTAL unique levels", len(all_levels))
    paths = [level_id_to_path(x) for x in sorted(all_levels)]
    print("sample paths", paths[:5])
    print("unmapped", sum(1 for p in paths if not p))


if __name__ == "__main__":
    main()
