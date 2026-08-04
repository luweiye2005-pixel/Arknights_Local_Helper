"""为 CI 桌面打包创建最小、合法的离线数据包。"""
import gzip
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "release_data"
out.mkdir(parents=True, exist_ok=True)
payload = {"schema_version": 1, "operator_briefs": [], "operators": {}, "skills": {}, "enemies": {}, "themes": [], "difficulties": {}, "theme_enemies": {}, "difficulty_mods": {}, "relics": {}, "rules": {}, "conditions": {}, "upgrade_groups": {}, "outer_buffs": {}, "meta": {"rule_version": 0}}
raw = gzip.compress(json.dumps(payload).encode("utf-8"))
(out / "data.json.gz").write_bytes(raw)
(out / "manifest.json").write_text(json.dumps({"schema_version": 1, "data_sha256": hashlib.sha256(raw).hexdigest()}), encoding="utf-8")
