"""Promote only mechanically verifiable parsed relic rules to curated migration rules."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.data.mysql_db import get_engine  # noqa: E402

AUDIT = ROOT / "reports" / "relic_api_audit_20260804.json"
PERCENT_ATTRS = {"atk_pct", "hp_pct", "def_pct", "damage_pct", "phys_damage_pct", "arts_damage_pct", "true_damage_pct", "elemental_damage_pct", "ignore_def_pct"}
SUPPORTED_ATTRS = PERCENT_ATTRS | {"atk_flat", "aspd", "res_flat", "true_damage"}
CONDITION_WORDS = ("时", "期间", "每", "首次", "距离", "低于", "高于", "生命值不高于", "生命值高于", "阻挡", "职业", "分支", "精英", "领袖", "BOSS")


def rule_is_clear(row: dict) -> bool:
    if row["target"] not in {"operator", "enemy"} or row["attr"] not in SUPPORTED_ATTRS or row.get("value_expr"):
        return False
    usage = str(row.get("usage_text") or "")
    value = abs(float(row.get("value") or 0) * (100 if row["attr"] in PERCENT_ATTRS else 1))
    numbers = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", usage)]
    if value and not any(abs(number - value) < 1e-6 for number in numbers):
        return False
    return not (any(word in usage for word in CONDITION_WORDS) and not row["has_conditions"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    passed = {row["relic_id"] for row in json.loads(AUDIT.read_text(encoding="utf-8"))["results"] if row["status"] == "passed"}
    engine = get_engine()
    with engine.begin() as conn:
        rows = [dict(row) for row in conn.execute(text("""
          SELECT rr.id,rr.relic_id,rr.target,rr.attr,rr.value,rr.value_expr,r.usage_text,
            EXISTS(SELECT 1 FROM relic_condition_params cp WHERE cp.relic_id=rr.relic_id) has_conditions,
            EXISTS(SELECT 1 FROM relic_upgrade_steps us WHERE us.relic_id=rr.relic_id AND us.equivalent_grade_min>0) is_upgrade
          FROM relic_effect_rules rr JOIN relics r ON r.id=rr.relic_id
          WHERE rr.source='parsed' AND rr.review_status<>'approved' AND rr.calculation_status='active'
          ORDER BY rr.relic_id,rr.id
        """)).mappings()]
        grouped = defaultdict(list)
        for row in rows:
            grouped[row["relic_id"]].append(row)
        eligible = sorted(
            rid for rid, rules in grouped.items()
            if (rid in passed or all(row["is_upgrade"] for row in rules))
            and all(rule_is_clear(row) for row in rules)
        )
        if args.apply and eligible:
            conn.execute(text("""
              UPDATE relic_effect_rules SET source='curated',rule_version=4,
                review_status='approved',reviewed_at=NOW(),note=CONCAT_WS('; ',note,'strict migration audit 20260804')
              WHERE source='parsed' AND review_status<>'approved' AND calculation_status='active'
                AND relic_id IN :ids
            """).bindparams(bindparam("ids", expanding=True)), {"ids": eligible})
    print(json.dumps({"eligible_relics": len(eligible), "eligible_rules": sum(len(grouped[rid]) for rid in eligible), "applied": args.apply}, ensure_ascii=False))


if __name__ == "__main__":
    main()
