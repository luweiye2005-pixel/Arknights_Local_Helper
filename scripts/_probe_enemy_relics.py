from app.data.mysql_db import get_engine
from sqlalchemy import text

c = get_engine().connect()
rows = c.execute(
    text(
        "SELECT name, usage_text FROM relics "
        "WHERE usage_text LIKE :p LIMIT 20"
    ),
    {"p": "%敌人%"},
).fetchall()
for r in rows:
    print("---", r[0])
    print((r[1] or "")[:120])
