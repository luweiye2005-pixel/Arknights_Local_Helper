# -*- coding: utf-8 -*-
import json
import urllib.request

body = {
    "enemy_id": "enemy_1007_slime",
    "theme_id": "rogue_1",
    "equivalent_grade": 0,
    "relic_ids": [],
}
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/calc/panel",
    data=json.dumps(body).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read().decode("utf-8"))
print("enemy", data.get("enemy"))
print("panel", data.get("enemy_final_panel"))
print("op", data.get("operator"), "final_op", data.get("final_panel"))
