"""Recompute MySQL operator skill parsed_effects from stored source fields."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.combat.attributes import skill_multiplier_and_duration  # noqa: E402
from app.data.mysql_db import get_engine  # noqa: E402

PARSED_KEYS = (
    "atk_scale", "atk_pct", "attack_speed", "base_attack_time",
    "damage_scale", "secondary_scale", "cnt", "hp_pct", "def_pct",
    "res_flat", "res_pct", "enemy_effects",
)


def decode(value):
    return json.loads(value) if isinstance(value, str) else (value or [])


def main() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        rows = list(conn.execute(text("""
            SELECT operator_id,skill_id,level,name,description,duration,blackboard
            FROM operator_skill_levels
            ORDER BY operator_id,skill_id,level
        """)).mappings())

    updates = []
    for row in rows:
        level = {
            "name": row["name"], "description": row["description"],
            "duration": row["duration"], "blackboard": decode(row["blackboard"]),
        }
        parsed = skill_multiplier_and_duration([level], 1)
        updates.append({
            "operator_id": row["operator_id"], "skill_id": row["skill_id"],
            "level": row["level"],
            "parsed_effects": json.dumps(
                {key: parsed[key] for key in PARSED_KEYS}, ensure_ascii=False,
            ),
        })

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE operator_skill_levels
            SET parsed_effects=CAST(:parsed_effects AS JSON)
            WHERE operator_id=:operator_id AND skill_id=:skill_id AND level=:level
        """), updates)
    print(json.dumps({"updated_skill_levels": len(updates)}))


if __name__ == "__main__":
    main()
