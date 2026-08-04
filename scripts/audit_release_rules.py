"""Classify relic rules that currently block an approved-only release build."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.mysql_db import get_engine  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with get_engine().connect() as conn:
        rows = [dict(row) for row in conn.execute(text("""
            SELECT rr.id, rr.relic_id, r.theme_id, r.name, rr.source,
                   rr.review_status, rr.calculation_status, rr.rule_version,
                   rr.target, rr.attr, rr.operation, rr.value, rr.value_expr,
                   r.usage_text,
                   EXISTS(
                     SELECT 1 FROM relic_effect_rules approved
                     WHERE approved.relic_id=rr.relic_id
                       AND approved.review_status='approved'
                       AND approved.calculation_status='active'
                   ) AS has_approved_active
                   ,EXISTS(
                     SELECT 1 FROM relics twin
                     JOIN relic_effect_rules approved ON approved.relic_id=twin.id
                     WHERE twin.id<>r.id AND twin.name=r.name
                       AND COALESCE(twin.usage_text,'')=COALESCE(r.usage_text,'')
                       AND approved.review_status='approved'
                       AND approved.calculation_status='active'
                   ) AS has_exact_approved_twin
                   ,EXISTS(
                     SELECT 1 FROM relic_condition_params cp
                     WHERE cp.relic_id=rr.relic_id
                   ) AS has_conditions
            FROM relic_effect_rules rr
            JOIN relics r ON r.id=rr.relic_id
            WHERE rr.review_status<>'approved' AND rr.calculation_status='active'
            ORDER BY r.theme_id,rr.relic_id,rr.display_order,rr.id
        """)).mappings()]

    summary = {
        "blocking_rules": len(rows),
        "blocking_relics": len({row["relic_id"] for row in rows}),
        "by_theme": dict(sorted(Counter(row["theme_id"] for row in rows).items())),
        "by_source": dict(sorted(Counter(row["source"] for row in rows).items())),
        "already_replaced_rules": sum(bool(row["has_approved_active"]) for row in rows),
        "unreplaced_rules": sum(not bool(row["has_approved_active"]) for row in rows),
        "unreplaced_relics": len({row["relic_id"] for row in rows if not row["has_approved_active"]}),
        "rules_with_exact_approved_twin": sum(bool(row["has_exact_approved_twin"]) for row in rows),
        "relics_with_exact_approved_twin": len({row["relic_id"] for row in rows if row["has_exact_approved_twin"]}),
    }
    percent_attrs = {"atk_pct", "hp_pct", "def_pct", "damage_pct", "phys_damage_pct", "arts_damage_pct", "true_damage_pct", "elemental_damage_pct", "ignore_def_pct"}
    condition_words = ("时", "期间", "每", "首次", "距离", "低于", "高于", "生命值不高于", "生命值高于", "阻挡", "职业", "分支", "精英", "领袖", "BOSS")
    supported_targets = {"operator", "enemy"}
    supported_attrs = percent_attrs | {"atk_flat", "aspd", "res_flat", "true_damage"}
    problems: list[dict] = []
    for row in rows:
        usage = str(row.get("usage_text") or "")
        reasons = []
        if row["target"] not in supported_targets or row["attr"] not in supported_attrs:
            reasons.append("unsupported target/attr")
        if row.get("value_expr"):
            reasons.append("parsed expression requires manual review")
        value = float(row.get("value") or 0)
        expected_number = abs(value * 100 if row["attr"] in percent_attrs else value)
        shown_numbers = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", usage)]
        if expected_number and not any(abs(x - expected_number) < 1e-6 for x in shown_numbers):
            reasons.append(f"value {expected_number:g} not found in description")
        if any(word in usage for word in condition_words) and not row["has_conditions"]:
            reasons.append("conditional wording without structured conditions")
        if reasons:
            problems.append({"relic_id": row["relic_id"], "name": row["name"], "reasons": reasons})
    summary["strict_check_problem_rules"] = len(problems)
    summary["strict_check_problem_relics"] = len({row["relic_id"] for row in problems})
    problem_ids = {row["relic_id"] for row in problems}
    summary["strict_check_unique_descriptions"] = len({
        (row["name"], row.get("usage_text") or "") for row in rows if row["relic_id"] in problem_ids
    })
    if args.output:
        by_relic = defaultdict(list)
        for row in rows:
            by_relic[row["relic_id"]].append(row)
        problem_map = defaultdict(set)
        for problem in problems:
            problem_map[problem["relic_id"]].update(problem["reasons"])
        lines = [
            "# 正式发布藏品规则复核清单", "",
            "> 本文由 `scripts/audit_release_rules.py` 生成，只列出不能安全自动迁移的旧解析规则。", "",
            f"- 待复核藏品：{len(problem_map)} 件", f"- 待复核规则：{len(problems)} 条", "",
        ]
        for rid in sorted(problem_map):
            relic_rules = by_relic[rid]
            first = relic_rules[0]
            lines += [
                f"## {first['name']}（`{rid}`）", "",
                f"- 主题：`{first['theme_id']}`",
                f"- 描述：{first.get('usage_text') or '（空）'}",
                f"- 风险：{'；'.join(sorted(problem_map[rid]))}",
                "- 当前规则：" + "；".join(
                    f"{row['target']}.{row['attr']} {row['operation']} {row.get('value')}"
                    for row in relic_rules
                ),
                "- 准备修复：根据描述补充结构化开关/层数/自动职业条件；无法影响敌我面板或最终伤害的部分标记 ignored；复核后改为 approved。",
                "",
            ]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nSTRICT_PROBLEMS")
    for problem in problems:
        print(f"{problem['relic_id']}\t{problem['name']}\t{'；'.join(problem['reasons'])}")
    print("\nUNREPLACED")
    for row in rows:
        if not row["has_approved_active"]:
            print("\t".join(str(row[key] or "") for key in ("theme_id", "relic_id", "name", "source", "target", "attr", "value_expr")))


if __name__ == "__main__":
    main()
