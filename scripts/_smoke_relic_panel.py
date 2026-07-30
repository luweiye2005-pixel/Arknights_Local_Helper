# -*- coding: utf-8 -*-
import json
import urllib.request

body = {
    "operator_id": "char_002_amiya",
    "elite": 2,
    "level": 80,
    "favor_percent": 100,
    "relic_ids": ["rogue_1_relic_a01"],
    "theme_id": "rogue_1",
    "equivalent_grade": 0,
}
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/calc/panel",
    data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read().decode("utf-8"))
print("base", data["base_panel"]["atk"], "final", data["final_panel"]["atk"])
print("atk_pct_from_relics", data["bonus"].get("atk_pct_from_relics"))
print("relics", data["relics_applied"])
