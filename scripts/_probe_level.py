# -*- coding: utf-8 -*-
import json
from pathlib import Path

import httpx

from app.config import settings

t = json.loads((settings.gamedata_path / "roguelike_topic_table.json").read_text(encoding="utf-8"))
d = t["details"]["rogue_1"]
stages = d.get("stages") or {}
print("stages", len(stages))
level_id = None
for sid, st in stages.items():
    if st.get("levelId") and not st.get("isBoss"):
        level_id = st["levelId"]
        print("pick", sid, level_id)
        break
if not level_id:
    level_id = next(st["levelId"] for st in stages.values() if st.get("levelId"))

parts = level_id.replace("\\", "/").split("/")
# Obt/Roguelike/RO1/level_rogue1_1-1 -> obt/roguelike/ro1/level_rogue1_1-1.json
rel = "zh_CN/gamedata/levels/" + "/".join(
    [parts[0].lower(), parts[1].lower(), parts[2].lower(), parts[3]]
) + ".json"
print("rel", rel)
url = "https://cdn.jsdelivr.net/gh/Kengxxiao/ArknightsGameData@master/" + rel
r = httpx.get(url, timeout=60, follow_redirects=True)
print("status", r.status_code, "bytes", len(r.content))
if r.status_code != 200:
    raise SystemExit(1)
lv = r.json()
print("top keys", list(lv.keys())[:25])
refs = lv.get("enemyDbRefs") or []
print("enemyDbRefs", len(refs))
if refs:
    print("ref0", refs[0])
# also check waves
waves = lv.get("waves") or []
print("waves", len(waves))
