"""One-time/idempotent migration of relic runtime rules into MySQL."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.mysql_db import get_engine, init_schema  # noqa: E402

VERSION = 1
CONDITION_FILE = ROOT / "data/patches/relic_conditions.json"
OUTER_FILE = ROOT / "data/patches/outer_buffs.json"
AUDIT_FILE = ROOT / "reports/relic_api_audit_20260804.json"

FIXED_RULES = {
    "rogue_1_relic_p29": [("enemy", "atk_pct", -0.15, "active")],
    "rogue_1_relic_c15": [
        ("operator", "atk_pct", -0.10, None),
        ("enemy", "atk_pct", 0.10, None), ("enemy", "def_pct", 0.10, None),
        ("enemy", "hp_pct", 0.10, None),
    ],
    "rogue_1_relic_m04": [("operator", x, 0.10, None) for x in ("atk_pct", "def_pct", "hp_pct")],
    "rogue_2_relic_fight_40": [("operator", x, 0.15, None) for x in ("atk_pct", "def_pct", "hp_pct")],
    "rogue_5_relic_legacy_149": [("operator", x, 0.20, None) for x in ("atk_pct", "def_pct", "hp_pct")],
    "rogue_6_relic_legacy_142": [("operator", x, 0.50, None) for x in ("atk_pct", "def_pct", "hp_pct")],
    "rogue_4_relic_fight_20": [("operator", "atk_pct", 0.50, "applies"), ("operator", "def_pct", 0.50, "applies")],
    "rogue_5_relic_return_9": [("operator", "atk_pct", 0.50, "applies"), ("operator", "def_pct", 0.50, "applies")],
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def insert_rule(conn, rid, target, attr, value, *, expr=None, when=None, status="active", reason=None,
                source="manual", review="approved", order=0, operation=None, note=None):
    operation = operation or ("multiply" if attr in {"damage_pct", "phys_damage_pct", "arts_damage_pct"} else "add")
    conn.execute(text("""
        INSERT INTO relic_effect_rules(
          relic_id,target,attr,operation,value,value_expr,when_param,damage_type,
          calculation_status,ignored_reason,source,rule_version,review_status,display_order,note,reviewed_at
        ) VALUES(:rid,:target,:attr,:op,:value,:expr,:when,NULL,:status,:reason,:source,:version,:review,:ord,:note,NOW())
        ON DUPLICATE KEY UPDATE value=VALUES(value),value_expr=VALUES(value_expr),when_param=VALUES(when_param),
          calculation_status=VALUES(calculation_status),ignored_reason=VALUES(ignored_reason),source=VALUES(source),
          rule_version=VALUES(rule_version),review_status=VALUES(review_status),note=VALUES(note),reviewed_at=NOW()
    """), {"rid": rid, "target": target, "attr": attr, "op": operation, "value": value,
             "expr": expr, "when": when, "status": status, "reason": reason, "source": source,
             "version": VERSION, "review": review, "ord": order, "note": note})


def main() -> None:
    init_schema()
    conditions = {k: v for k, v in load(CONDITION_FILE).items() if not k.startswith("_")}
    outers = {k: v for k, v in load(OUTER_FILE).items() if not k.startswith("_")}
    audit = load(AUDIT_FILE)
    suspected = {row["relic_id"]: (row.get("problems") or ["当前模型不支持"])[0]
                 for row in audit.get("results", []) if row.get("status") == "suspected"}
    engine = get_engine()
    with engine.begin() as conn:
        # Regenerate only non-approved rules. Curated/approved rows survive reruns.
        conn.execute(text("DELETE FROM relic_condition_params WHERE review_status<>'approved'"))
        conn.execute(text("DELETE FROM relic_effect_rules WHERE review_status<>'approved'"))

        legacy = conn.execute(text("SELECT * FROM relic_effects ORDER BY relic_id,id")).mappings().all()
        for index, row in enumerate(legacy):
            insert_rule(conn, row["relic_id"], row["target"], row["attr"], float(row["value"]),
                        source=row["source"], review="approved" if row["source"] == "manual" else "pending",
                        order=index, note=row["note"])

        for rid, schema in conditions.items():
            for index, param in enumerate(schema.get("params") or []):
                ptype = param.get("type") or "number"
                default = 0  # all manual conditions are off/zero by product decision
                auto = param.get("auto")
                conn.execute(text("""
                    INSERT INTO relic_condition_params(
                      relic_id,param_id,param_type,label,default_value,min_value,max_value,step_value,unit,
                      auto_rule,display_order,rule_version,review_status
                    ) VALUES(:rid,:pid,:ptype,:label,:default,:min,:max,:step,:unit,CAST(:auto AS JSON),:ord,:version,'approved')
                    ON DUPLICATE KEY UPDATE param_type=VALUES(param_type),label=VALUES(label),default_value=VALUES(default_value),
                      min_value=VALUES(min_value),max_value=VALUES(max_value),step_value=VALUES(step_value),unit=VALUES(unit),
                      auto_rule=VALUES(auto_rule),rule_version=VALUES(rule_version),review_status='approved'
                """), {"rid": rid, "pid": param["id"], "ptype": ptype, "label": param.get("label") or param["id"],
                         "default": default, "min": param.get("min", 0), "max": param.get("max"),
                         "step": param.get("step", 1), "unit": param.get("unit"),
                         "auto": json.dumps(auto, ensure_ascii=False) if auto else "null", "ord": index, "version": VERSION})
            if schema.get("params"):
                conn.execute(text("DELETE FROM relic_effect_rules WHERE relic_id=:rid AND target='operator'"), {"rid": rid})
                for index, effect in enumerate(schema.get("operator_effects") or []):
                    insert_rule(conn, rid, "operator", effect.get("attr") or "", float(effect.get("value") or 0),
                                expr=effect.get("expr"), when=effect.get("when"), order=index,
                                source="manual", review="approved", note=schema.get("name"))

        # Explicitly repair the seven confirmed failures, replacing bad operator rules.
        for rid, rules in FIXED_RULES.items():
            conn.execute(text("DELETE FROM relic_effect_rules WHERE relic_id=:rid AND target IN ('operator','enemy')"), {"rid": rid})
            for index, (target, attr, value, when) in enumerate(rules):
                insert_rule(conn, rid, target, attr, value, when=when, order=index, note="confirmed audit fix")

        for theme_id, buff in outers.items():
            conn.execute(text("""
                INSERT INTO theme_outer_buffs(theme_id,name,atk_pct,hp_pct,def_pct,aspd,note,rule_version,review_status)
                VALUES(:id,:name,:atk,:hp,:def,:aspd,:note,:version,'approved')
                ON DUPLICATE KEY UPDATE name=VALUES(name),atk_pct=VALUES(atk_pct),hp_pct=VALUES(hp_pct),
                  def_pct=VALUES(def_pct),aspd=VALUES(aspd),note=VALUES(note),rule_version=VALUES(rule_version)
            """), {"id": theme_id, "name": buff.get("name"), "atk": buff.get("atk_pct", 0),
                     "hp": buff.get("hp_pct", 0), "def": buff.get("def_pct", 0), "aspd": buff.get("aspd", 0),
                     "note": buff.get("note"), "version": VERSION})

        # Convert auditable distance/first-hit ratios from the unresolved list
        # into bounded manual inputs. Everything else remains explicitly ignored.
        if suspected:
            relic_texts = conn.execute(text("SELECT id,usage_text FROM relics")).mappings().all()
            for row in relic_texts:
                rid, usage = row["id"], str(row["usage_text"] or "")
                if rid not in suspected:
                    continue
                maximum = re.search(r"距离[^。；]{0,40}最高\s*(\d+(?:\.\d+)?)%", usage)
                first_hit = re.search(r"首次[^。；]{0,30}伤害提升至\s*(\d+(?:\.\d+)?)%", usage)
                if maximum:
                    max_pct = float(maximum.group(1))
                    conn.execute(text("""
                      INSERT INTO relic_condition_params(relic_id,param_id,param_type,label,default_value,min_value,max_value,step_value,unit,display_order,rule_version,review_status)
                      VALUES(:rid,'distance_bonus_pct','number','当前距离伤害加成',0,0,:max,1,'%',0,:version,'approved')
                      ON DUPLICATE KEY UPDATE max_value=VALUES(max_value),default_value=0,review_status='approved'
                    """), {"rid": rid, "max": max_pct, "version": VERSION})
                    insert_rule(conn, rid, "operator", "damage_pct", 0, expr="distance_bonus_pct/100",
                                source="manual", review="approved", note="manual distance ratio")
                elif first_hit:
                    factor = float(first_hit.group(1)) / 100.0
                    conn.execute(text("""
                      INSERT INTO relic_condition_params(relic_id,param_id,param_type,label,default_value,min_value,max_value,step_value,display_order,rule_version,review_status)
                      VALUES(:rid,'applies','toggle','当前攻击满足首次伤害等描述条件',0,0,1,1,0,:version,'approved')
                      ON DUPLICATE KEY UPDATE default_value=0,review_status='approved'
                    """), {"rid": rid, "version": VERSION})
                    insert_rule(conn, rid, "operator", "damage_pct", factor - 1.0, when="applies",
                                source="manual", review="approved", note="manual first-hit condition")

        for rid, reason in suspected.items():
            has_active = conn.execute(text("SELECT 1 FROM relic_effect_rules WHERE relic_id=:rid AND calculation_status='active' LIMIT 1"), {"rid": rid}).first()
            if has_active:
                continue
            insert_rule(conn, rid, "meta", "ignored", 0, status="ignored", reason=reason,
                        source="manual", review="approved", order=9999, note="20260804 full API audit")

        # Every catalog item gets an explicit rule status.
        missing = conn.execute(text("""
            SELECT x.id FROM relics x LEFT JOIN relic_effect_rules r ON r.relic_id=x.id
            WHERE r.id IS NULL
        """)).fetchall()
        for (rid,) in missing:
            insert_rule(conn, rid, "meta", "ignored", 0, status="ignored",
                        reason="非战斗功能或当前面板/单次伤害模型不适用", order=9999)

        counts = dict(conn.execute(text("""
          SELECT calculation_status,COUNT(*) count FROM relic_effect_rules GROUP BY calculation_status
        """)).fetchall())
    print(json.dumps({"rule_counts": counts, "condition_schemas": len(conditions),
                      "outer_buffs": len(outers), "audited_ignored": len(suspected)}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
