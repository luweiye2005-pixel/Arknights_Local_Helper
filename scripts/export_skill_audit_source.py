"""Read-only MySQL export used by the skill autofill audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.mysql_db import get_engine  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def decoded(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def main() -> None:
    with get_engine().connect() as conn:
        counts = {
            "operators": conn.execute(text("SELECT COUNT(*) FROM operators")).scalar_one(),
            "operator_skills": conn.execute(text("SELECT COUNT(*) FROM operator_skills")).scalar_one(),
            "operator_skill_levels": conn.execute(text("SELECT COUNT(*) FROM operator_skill_levels")).scalar_one(),
        }
        operators = [dict(row) for row in conn.execute(
            text("SELECT id,name FROM operators ORDER BY id")
        ).mappings()]
        rows = conn.execute(text("""
            SELECT osl.operator_id,o.name AS operator_name,os.skill_index,os.max_level,
                   osl.skill_id,osl.level,osl.name,osl.description,osl.blackboard,
                   osl.parsed_effects
            FROM operator_skill_levels osl
            JOIN operator_skills os
              ON os.operator_id=osl.operator_id AND os.skill_id=osl.skill_id
            JOIN operators o ON o.id=osl.operator_id
            WHERE osl.level=7 OR osl.level=os.max_level
            ORDER BY osl.operator_id,os.skill_index,osl.level
        """)).mappings()
        levels = []
        for row in rows:
            item = dict(row)
            item["blackboard"] = decoded(item["blackboard"]) or []
            item["parsed_effects"] = decoded(item["parsed_effects"]) or {}
            levels.append(item)
    print(json.dumps({"counts": counts, "operators": operators, "levels": levels}, ensure_ascii=False))


if __name__ == "__main__":
    main()
