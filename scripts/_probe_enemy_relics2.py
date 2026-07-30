# -*- coding: utf-8 -*-
from app.data.mysql_db import get_engine
from sqlalchemy import text

c = get_engine().connect()
patterns = ["%敌人生命%", "%敌人攻击%", "%敌人防御%", "%所有敌人%"]
for p in patterns:
    rows = c.execute(
        text("SELECT name, usage_text FROM relics WHERE usage_text LIKE :p LIMIT 8"),
        {"p": p},
    ).fetchall()
    print("===", p, "count sample", len(rows))
    for r in rows:
        print(r[0], "|", (r[1] or "")[:100])
