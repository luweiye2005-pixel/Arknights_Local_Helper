"""Audit rogue_6 relic descriptions against structured rules and conditions."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.mysql_db import get_engine, init_schema  # noqa: E402

COMBAT = ("攻击", "生命", "防御", "法抗", "法术抗性", "攻速", "攻击速度", "伤害", "无视")
CONDITIONAL = ("时，", "时,", "期间", "若", "首次", "每次", "范围内", "生命值低于", "生命值高于")
STACKED = ("每层", "可叠加", "每拥有", "每有", "层【")
ENEMY_KIND = ("猎犬proto", "居民", "萨卡兹", "精英", "领袖", "BOSS", "首领")
TYPE_WORDS = {"物理伤害": "phys_damage_pct", "法术伤害": "arts_damage_pct", "真实伤害": "true_damage_pct", "元素伤害": "elemental_damage_pct"}


def main() -> None:
    init_schema()
    with get_engine().connect() as conn:
        relics = [dict(r) for r in conn.execute(text("""
            SELECT id,name,usage_text FROM relics
            WHERE theme_id='rogue_6' AND id NOT IN (
              SELECT relic_id FROM relic_upgrade_steps WHERE equivalent_grade_min > 0
            ) ORDER BY order_id,id
        """)).mappings()]
        rules = defaultdict(list)
        for row in conn.execute(text("SELECT * FROM relic_effect_rules WHERE relic_id LIKE 'rogue_6_%' ORDER BY display_order,id")).mappings():
            rules[row["relic_id"]].append(dict(row))
        params = defaultdict(list)
        for row in conn.execute(text("SELECT * FROM relic_condition_params WHERE relic_id LIKE 'rogue_6_%' ORDER BY display_order,param_id")).mappings():
            params[row["relic_id"]].append(dict(row))

    rows = []
    for relic in relics:
        rid, usage = relic["id"], relic.get("usage_text") or ""
        rr, pp = rules[rid], params[rid]
        active = [r for r in rr if r.get("calculation_status") == "active"]
        ignored_rule = any(r.get("calculation_status") == "ignored" for r in rr)
        relevant = any(word in usage for word in COMBAT)
        issues = []
        if relevant and not active and not any(r.get("calculation_status") == "ignored" for r in rr):
            issues.append("描述涉及面板/伤害，但没有 active 或 ignored 规则")
        if relevant and not ignored_rule and any(word in usage for word in STACKED) and not any(p.get("param_type") == "number" for p in pp):
            issues.append("描述含叠层，但没有数字层数参数")
        if relevant and not ignored_rule and any(word in usage for word in ENEMY_KIND) and not any(p.get("param_type") == "toggle" for p in pp):
            issues.append("描述限定敌人类型，但没有手动判断开关")
        if relevant and any(word in usage for word in CONDITIONAL) and active and not pp and not all(r.get("target") == "meta" for r in active):
            issues.append("描述含触发条件，但规则按常驻生效")
        attrs = {str(r.get("attr")) for r in active}
        for wording, expected in TYPE_WORDS.items():
            if rid == "rogue_6_relic_legacy_121":
                continue  # 2000 法伤是忽略的事件伤害；10秒受伤+30%为通用类型。
            if wording in usage and any(a.endswith("damage_pct") or a == "damage_pct" for a in attrs) and expected not in attrs:
                issues.append(f"伤害类型可能错误：{wording} 应使用 {expected}")
        if not relevant:
            status = "范围外"
        elif issues:
            status = "需复核"
        elif active or rr:
            status = "结构一致"
        else:
            status = "需复核"
        rows.append((relic, status, issues, active, pp))

    report = ROOT / "reports" / "rogue6_relic_logic_audit_20260804.md"
    counts = {s: sum(row[1] == s for row in rows) for s in ("结构一致", "需复核", "范围外")}
    lines = [
        "# 沉沦者的黑流树海：全部藏品计算语义审计", "",
        "审计范围：敌我面板与最终伤害；技力、部署费用、招募、资源、事件等列为范围外。", "",
        f"- 藏品总数：{len(rows)}", f"- 结构一致：{counts['结构一致']}",
        f"- 需人工复核：{counts['需复核']}", f"- 范围外：{counts['范围外']}", "",
        "## 需复核清单", "",
    ]
    for relic, status, issues, active, pp in rows:
        if status != "需复核":
            continue
        lines += [f"### {relic['name']}（`{relic['id']}`）", "", f"- 描述：{relic.get('usage_text') or ''}",
                  f"- 风险：{'；'.join(issues)}", f"- 当前规则：{[(r.get('target'), r.get('attr'), r.get('value'), r.get('value_expr'), r.get('when_param')) for r in active]}",
                  f"- 当前参数：{[(p.get('param_id'), p.get('param_type'), p.get('label')) for p in pp]}", ""]
    lines += ["## 全部藏品索引", "", "| ID | 名称 | 分类 |", "|---|---|---|"]
    lines += [f"| `{r[0]['id']}` | {r[0]['name']} | {r[1]} |" for r in rows]
    report.write_text("\n".join(lines), encoding="utf-8")
    print({"total": len(rows), **counts, "report": str(report)})


if __name__ == "__main__":
    main()
