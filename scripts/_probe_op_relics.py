# -*- coding: utf-8 -*-
from app.combat.relics import build_relic_modifiers, parse_relic_text
from app.data.mysql_db import get_engine
from sqlalchemy import text

c = get_engine().connect()
rows = c.execute(
    text(
        """
        SELECT r.id, r.name, r.usage_text
        FROM relics r
        WHERE r.theme_id='rogue_1'
          AND (r.usage_text LIKE '%攻击力%提升%' OR r.usage_text LIKE '%攻击力+%'
               OR r.usage_text LIKE '%攻击提升%' OR r.usage_text LIKE '%攻速%')
        LIMIT 15
        """
    )
).fetchall()
print("operator-like texts:")
for rid, name, usage in rows:
    parsed = parse_relic_text(name or "", usage or "")
    built = build_relic_modifiers(relic_ids=[rid])
    print(name, "| parsed_atk", parsed.atk_pct, "aspd", parsed.aspd, "| built", built.atk_pct, built.aspd)
    print(" ", (usage or "")[:70])
