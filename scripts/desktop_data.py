"""开发者数据命令：sync / build-data / audit / package。"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.data import mysql_db as db  # noqa: E402

SCHEMA_VERSION = 1


def _default(value):
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, Decimal): return float(value)
    raise TypeError(type(value).__name__)


def _rows(conn, sql: str) -> list[dict]: return [dict(x) for x in conn.execute(text(sql)).mappings()]


def build_data(output: Path, *, allow_pending: bool = False) -> dict:
    db.init_schema(); output.mkdir(parents=True, exist_ok=True)
    with db.get_engine().connect() as conn:
        pending = int(conn.execute(text("SELECT COUNT(*) FROM relic_effect_rules WHERE review_status<>'approved' AND calculation_status='active'")).scalar() or 0)
        if pending and not allow_pending:
            raise RuntimeError(f"仍有 {pending} 条 active 藏品规则未 approved，拒绝生成正式数据包")
        operator_briefs = db.search_operators(limit=20000)
        operators = {x["id"]: db.get_operator_detail(x["id"]) for x in operator_briefs}
        skills = {x["id"]: db.get_operator_skills(x["id"]) for x in operator_briefs}
        enemies, level_map = {}, defaultdict(list)
        for lv in _rows(conn, "SELECT * FROM enemy_levels ORDER BY enemy_id,level_index"):
            level_map[lv["enemy_id"]].append({"attributes": {"hp": lv["hp"], "atk": lv["atk"], "def": lv["def_stat"], "magic_resistance": lv["magic_resistance"], "move_speed": lv["move_speed"], "attack_speed": lv["attack_speed"], "range_radius": lv["range_radius"]}})
        for en in _rows(conn, "SELECT * FROM enemies ORDER BY id"):
            enemies[en["id"]] = {"brief": {"id": en["id"], "name": en["name"], "enemy_level": en["enemy_level"], "description": en["description"]}, "levels": level_map[en["id"]]}
        relics = {}
        for r in _rows(conn, "SELECT r.*,t.name theme_name FROM relics r LEFT JOIN themes t ON t.id=r.theme_id"):
            relics[r["id"]] = {"id": r["id"], "theme": r["theme_id"], "theme_name": r["theme_name"], "name": r["name"], "usage": r["usage_text"], "description": r["description"], "icon_id": r["icon_id"], "order_id": r["order_id"]}
        rules = defaultdict(list)
        rule_where = "review_status='approved'" if not allow_pending else "1=1"
        for r in _rows(conn, f"SELECT * FROM relic_effect_rules WHERE {rule_where} ORDER BY relic_id,display_order,id"):
            rules[r["relic_id"]].append(r)
        groups = defaultdict(list)
        for s in _rows(conn, "SELECT * FROM relic_upgrade_steps ORDER BY group_id,equivalent_grade_min"):
            groups[s["group_id"]].append({"relic_id": s["relic_id"], "equivalent_grade_min": s["equivalent_grade_min"]})
        theme_enemies = defaultdict(list)
        for x in _rows(conn, "SELECT * FROM theme_enemies ORDER BY theme_id,enemy_id"): theme_enemies[x["theme_id"]].append(x["enemy_id"])
        difficulties = defaultdict(list)
        for x in _rows(conn, "SELECT * FROM theme_difficulties ORDER BY theme_id,grade,equivalent_grade"):
            x["key"] = f"{x['mode_difficulty']}:{int(x['grade'])}"; difficulties[x["theme_id"]].append(x)
        difficulty_mods = defaultdict(list)
        for x in _rows(conn, "SELECT * FROM difficulty_stat_mods ORDER BY theme_id,equivalent_grade,id"): difficulty_mods[x["theme_id"]].append(x)
        payload = {"schema_version": SCHEMA_VERSION, "operator_briefs": operator_briefs, "operators": operators, "skills": skills, "enemies": enemies, "themes": db.list_themes_db(), "difficulties": difficulties, "theme_enemies": theme_enemies, "difficulty_mods": difficulty_mods, "relics": relics, "rules": rules, "conditions": db.get_relic_condition_schemas(), "upgrade_groups": groups, "outer_buffs": db.get_theme_outer_buffs(), "meta": {"generated_at": datetime.now(timezone.utc).isoformat(), "rule_version": max((int(r.get('rule_version') or 0) for values in rules.values() for r in values), default=0), "pending_in_source": pending}}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=_default).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9); (output / "data.json.gz").write_bytes(compressed)
    manifest = {"schema_version": SCHEMA_VERSION, "generated_at": payload["meta"]["generated_at"], "rule_version": payload["meta"]["rule_version"], "data_sha256": hashlib.sha256(compressed).hexdigest(), "uncompressed_bytes": len(raw), "compressed_bytes": len(compressed), "source": "local-curated-mysql"}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def audit() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_rogue6_relic_logic.py")], check=True, cwd=ROOT / "backend")
    subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"], check=True, cwd=ROOT / "backend")


def package(source: Path, output: Path) -> None:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    data = (source / "data.json.gz").read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest["data_sha256"]: raise RuntimeError("数据包校验失败")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for path in source.rglob("*"):
            if path.is_file(): z.write(path, path.relative_to(source))


def main() -> None:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync"); build = sub.add_parser("build-data"); build.add_argument("--output", type=Path, default=ROOT / "release_data"); build.add_argument("--allow-pending", action="store_true")
    sub.add_parser("audit"); pack = sub.add_parser("package"); pack.add_argument("--source", type=Path, default=ROOT / "release_data"); pack.add_argument("--output", type=Path, default=ROOT / "dist" / "offline-data.zip")
    args = parser.parse_args()
    if args.command == "sync": subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_gamedata.py")], check=True)
    elif args.command == "build-data": print(json.dumps(build_data(args.output, allow_pending=args.allow_pending), ensure_ascii=False))
    elif args.command == "audit": audit()
    else: package(args.source, args.output)


if __name__ == "__main__": main()
