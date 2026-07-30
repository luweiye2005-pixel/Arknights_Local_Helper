# -*- coding: utf-8 -*-
from app.combat.relics import build_relic_modifiers
from app.data.mysql_db import get_engine
from sqlalchemy import text

c = get_engine().connect()
rows = c.execute(
    text(
        """
        SELECT r.id, r.name, r.usage_text
        FROM relics r
        LEFT JOIN relic_effects e ON e.relic_id = r.id
        WHERE e.id IS NULL AND r.usage_text LIKE :p
        LIMIT 5
        """
    ),
    {"p": "%攻击%"},
).fetchall()
print("no-effect relics:")
for r in rows:
    print(r[0], r[1], (r[2] or "")[:60])
    print("  mods=", build_relic_modifiers(relic_ids=[r[0]]))

print(
    "with effects",
    c.execute(text("SELECT COUNT(DISTINCT relic_id) FROM relic_effects")).scalar(),
)
print("total relics", c.execute(text("SELECT COUNT(*) FROM relics")).scalar())

# upgrade: base has effect, variant may not
row = c.execute(
    text(
        """
        SELECT s1.relic_id AS base_id, s2.relic_id AS var_id, s2.equivalent_grade_min
        FROM relic_upgrade_steps s1
        JOIN relic_upgrade_steps s2 ON s2.group_id = s1.group_id
        JOIN relic_effects e ON e.relic_id = s1.relic_id
        WHERE s1.equivalent_grade_min = 0 AND s2.equivalent_grade_min > 0
        LIMIT 5
        """
    )
).fetchall()
print("upgrade cases:")
for r in row:
    print(r)
    print("  eq0", build_relic_modifiers(relic_ids=[r[0]], equivalent_grade=0).atk_pct)
    print("  eq", r[2], build_relic_modifiers(relic_ids=[r[0]], equivalent_grade=int(r[2])).atk_pct)
