# -*- coding: utf-8 -*-
from app.combat.panel import calculate_panel
from app.combat.relics import build_relic_modifiers
from app.data.mysql_db import get_engine, get_relic_effects_merged, resolve_relic_for_grade
from sqlalchemy import text

c = get_engine().connect()
# Find base with effects where upgraded variant has NONE
rows = c.execute(
    text(
        """
        SELECT s1.relic_id base_id, s2.relic_id var_id, s2.equivalent_grade_min eq,
               (SELECT COUNT(*) FROM relic_effects e WHERE e.relic_id=s1.relic_id) base_n,
               (SELECT COUNT(*) FROM relic_effects e WHERE e.relic_id=s2.relic_id) var_n
        FROM relic_upgrade_steps s1
        JOIN relic_upgrade_steps s2 ON s2.group_id=s1.group_id AND s2.equivalent_grade_min>0
        WHERE s1.equivalent_grade_min=0
        HAVING base_n>0 AND var_n=0
        LIMIT 10
        """
    )
).fetchall()
print("base has effects, variant none:", len(rows))
for r in rows[:8]:
    print(r)
    base, var, eq = r[0], r[1], int(r[2])
    print("  merged eq0", get_relic_effects_merged([base], 0))
    print("  merged eq", eq, get_relic_effects_merged([base], eq))
    print("  mods eq", eq, build_relic_modifiers(relic_ids=[base], equivalent_grade=eq))
