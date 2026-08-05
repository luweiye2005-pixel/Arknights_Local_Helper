"""藏品、主题与规则的 MySQL 查询。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.data.mysql_core import get_engine, init_schema

def search_relics(
    theme: str | None = None,
    q: str | None = None,
    limit: int = 500,
    equivalent_grade: int | None = None,
) -> list[dict]:
    init_schema()
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if theme:
        clauses.append("r.theme_id = :theme")
        params["theme"] = theme
    if q and q.strip():
        clauses.append("(r.name LIKE :like OR r.id LIKE :like OR r.usage_text LIKE :like)")
        params["like"] = f"%{q.strip()}%"
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT r.id, r.theme_id AS theme, t.name AS theme_name, r.name,
               r.usage_text AS `usage`, r.description, r.icon_id, r.order_id
        FROM relics r
        LEFT JOIN themes t ON t.id = r.theme_id
        {where}
        ORDER BY r.order_id ASC, r.name ASC
        LIMIT :limit
    """
    with get_engine().connect() as conn:
        items = [dict(r) for r in conn.execute(text(sql), params).mappings().all()]
        # 列表默认只展示升级链「根」藏品，变体通过 equivalent_grade 解析展示
        upgrade_variants = {
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT relic_id FROM relic_upgrade_steps
                    WHERE equivalent_grade_min > 0
                    """
                )
            ).fetchall()
        }
        items = [d for d in items if d["id"] not in upgrade_variants]
        for d in items:
            d["icon_url"] = f"/api/v1/assets/relic/{d['id']}"
            if equivalent_grade is not None:
                resolved = resolve_relic_for_grade(d["id"], int(equivalent_grade), conn=conn)
                if resolved and resolved["id"] != d["id"]:
                    d["resolved_id"] = resolved["id"]
                    d["resolved_name"] = resolved.get("name")
                    d["name"] = resolved.get("name") or d["name"]
                    d["usage"] = resolved.get("usage") or d["usage"]
                    d["icon_id"] = resolved.get("icon_id") or d["icon_id"]
                    # 变体图常与根藏品共用；URL 仍指向变体，服务端会回退根图
                    d["icon_url"] = f"/api/v1/assets/relic/{resolved['id']}"
                    d["icon_fallback_id"] = d["id"]
            # attach compact effects（变体无效果时回退根藏品）
            rid = d.get("resolved_id") or d["id"]
            eff = conn.execute(
                text("SELECT attr,value,target FROM relic_effect_rules WHERE relic_id=:id AND calculation_status='active' AND attr<>'ignored'"),
                {"id": rid},
            ).mappings().all()
            if not eff and d.get("resolved_id"):
                eff = conn.execute(
                    text("SELECT attr,value,target FROM relic_effect_rules WHERE relic_id=:id AND calculation_status='active' AND attr<>'ignored'"),
                    {"id": d["id"]},
                ).mappings().all()
            d["effects"] = [dict(e) for e in eff]
        return items


def list_themes_db() -> list[dict]:
    init_schema()
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT t.id, t.name, COUNT(r.id) AS relic_count
                FROM themes t
                LEFT JOIN relics r
                  ON r.theme_id = t.id
                 AND r.id NOT IN (
                   SELECT relic_id FROM relic_upgrade_steps WHERE equivalent_grade_min > 0
                 )
                GROUP BY t.id, t.name
                ORDER BY t.id
                """
            )
        ).mappings().all()
        return [dict(r) for r in rows]


def list_theme_difficulties(theme_id: str) -> list[dict]:
    init_schema()
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, theme_id, mode_difficulty, grade, equivalent_grade, name,
                       score_factor, rule_desc, color, sort_id
                FROM theme_difficulties
                WHERE theme_id=:tid
                ORDER BY
                  CASE mode_difficulty
                    WHEN 'NORMAL' THEN 0
                    WHEN 'EASY' THEN 1
                    WHEN 'MONTH_TEAM' THEN 2
                    WHEN 'CHALLENGE' THEN 3
                    ELSE 9
                  END,
                  grade ASC,
                  equivalent_grade ASC,
                  sort_id IS NULL, sort_id
                """
            ),
            {"tid": theme_id},
        ).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["key"] = f"{d['mode_difficulty']}:{int(d['grade'])}"
            out.append(d)
        return out


def get_relic_row(relic_id: str) -> dict | None:
    init_schema()
    with get_engine().connect() as conn:
        r = conn.execute(
            text(
                """
                SELECT r.*, t.name AS theme_name
                FROM relics r LEFT JOIN themes t ON t.id=r.theme_id
                WHERE r.id=:id
                """
            ),
            {"id": relic_id},
        ).mappings().first()
        if not r:
            return None
        d = dict(r)
        d["theme"] = d.pop("theme_id")
        d["usage"] = d.pop("usage_text")
        d["effects"] = [
            dict(e)
            for e in conn.execute(
                text("""
                  SELECT attr,value,target,source,note,operation,value_expr,when_param,
                         calculation_status,rule_version,review_status
                  FROM relic_effect_rules
                  WHERE relic_id=:id AND calculation_status='active' AND attr<>'ignored'
                  ORDER BY display_order,id
                """),
                {"id": relic_id},
            ).mappings().all()
        ]
        statuses = conn.execute(text("""
          SELECT calculation_status,ignored_reason FROM relic_effect_rules
          WHERE relic_id=:id ORDER BY calculation_status='active' DESC,id
        """), {"id": relic_id}).mappings().all()
        d["calculation_status"] = "active" if any(x["calculation_status"] == "active" for x in statuses) else "ignored"
        d["ignored_reason"] = next((x["ignored_reason"] for x in statuses if x["calculation_status"] == "ignored" and x["ignored_reason"]), None)
        d["icon_url"] = f"/api/v1/assets/relic/{relic_id}"
        return d


def resolve_relic_for_grade(relic_id: str, equivalent_grade: int, conn=None) -> dict | None:
    """按升级链把 relic_id 解析到当前难度生效的变体。"""
    own = conn is None
    if own:
        conn = get_engine().connect()
    try:
        # 找到包含该 relic 的组，取 <= grade 最高一步
        step = conn.execute(
            text(
                """
                SELECT s2.relic_id
                FROM relic_upgrade_steps s1
                JOIN relic_upgrade_steps s2 ON s2.group_id = s1.group_id
                WHERE s1.relic_id = :rid AND s2.equivalent_grade_min <= :eq
                ORDER BY s2.equivalent_grade_min DESC
                LIMIT 1
                """
            ),
            {"rid": relic_id, "eq": equivalent_grade},
        ).first()
        target_id = step[0] if step else relic_id
        row = conn.execute(
            text(
                """
                SELECT id, name, usage_text AS `usage`, description, icon_id, theme_id AS theme, order_id
                FROM relics WHERE id=:id
                """
            ),
            {"id": target_id},
        ).mappings().first()
        return dict(row) if row else None
    finally:
        if own:
            conn.close()


def get_relic_rule_rows(relic_ids: list[str], equivalent_grade: int = 0) -> list[dict]:
    """Return active/manual MySQL relic rules for resolved relic ids."""
    init_schema()
    rows: list[dict] = []
    with get_engine().connect() as conn:
        for rid in relic_ids or []:
            resolved = resolve_relic_for_grade(rid, equivalent_grade) or {"id": rid}
            actual = resolved.get("id") or rid
            found = conn.execute(text("""
                SELECT r.*,x.name AS relic_name
                FROM relic_effect_rules r JOIN relics x ON x.id=r.relic_id
                WHERE r.relic_id=:rid
                ORDER BY r.display_order,r.id
            """), {"rid": actual}).mappings().all()
            rows.extend(dict(row) for row in found)
    return rows


def get_relic_condition_schemas(theme_id: str | None = None) -> dict[str, dict]:
    init_schema()
    where = "WHERE x.theme_id=:theme" if theme_id else ""
    params = {"theme": theme_id} if theme_id else {}
    with get_engine().connect() as conn:
        param_rows = conn.execute(text(f"""
            SELECT p.*,x.name AS relic_name FROM relic_condition_params p
            JOIN relics x ON x.id=p.relic_id {where}
            ORDER BY p.relic_id,p.display_order,p.param_id
        """), params).mappings().all()
        rule_rows = conn.execute(text(f"""
            SELECT r.* FROM relic_effect_rules r
            JOIN relics x ON x.id=r.relic_id
            {where}
            ORDER BY r.relic_id,r.display_order,r.id
        """), params).mappings().all()
    out: dict[str, dict] = {}
    for row in param_rows:
        auto = row["auto_rule"]
        if isinstance(auto, str):
            auto = json.loads(auto)
        item = {
            "id": row["param_id"], "type": row["param_type"], "label": row["label"],
            "default": bool(row["default_value"]) if row["param_type"] == "toggle" else float(row["default_value"]),
        }
        if row["min_value"] is not None: item["min"] = float(row["min_value"])
        if row["max_value"] is not None: item["max"] = float(row["max_value"])
        if row["step_value"] is not None: item["step"] = float(row["step_value"])
        if row["unit"]: item["unit"] = row["unit"]
        if auto: item["auto"] = auto
        out.setdefault(row["relic_id"], {"name": row["relic_name"], "params": [], "operator_effects": [], "replace_operator_panel": True})["params"].append(item)
    for row in rule_rows:
        if row["relic_id"] not in out or row["calculation_status"] == "ignored" or row["target"] != "operator":
            continue
        effect = {"attr": row["attr"], "value": float(row["value"])}
        if row["value_expr"]: effect["expr"] = row["value_expr"]
        if row["when_param"]: effect["when"] = row["when_param"]
        effect["operation"] = row["operation"]
        out.setdefault(row["relic_id"], {"name": row["relic_id"], "params": [], "operator_effects": [], "replace_operator_panel": True})["operator_effects"].append(effect)
    return {key: value for key, value in out.items() if value["params"] or value["operator_effects"]}


def get_theme_outer_buffs() -> dict[str, dict]:
    init_schema()
    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT * FROM theme_outer_buffs")).mappings().all()
    return {row["theme_id"]: {key: row[key] for key in ("name", "atk_pct", "hp_pct", "def_pct", "aspd", "note")} for row in rows}


def get_relic_effects_merged(relic_ids: list[str], equivalent_grade: int = 0) -> list[dict]:
    """解析升级链后返回 effect 行列表；变体无效果时回退到同链更低档。"""
    init_schema()
    with get_engine().connect() as conn:
        effects: list[dict] = []
        seen_ids: set[str] = set()
        for rid in relic_ids:
            resolved = resolve_relic_for_grade(rid, equivalent_grade, conn=conn)
            target_id = (resolved or {}).get("id") or rid
            # 收集同组内 <= grade 的全部候选（高→低），取第一份非空规则
            candidates: list[str] = [target_id]
            steps = conn.execute(
                text(
                    """
                    SELECT s2.relic_id, s2.equivalent_grade_min
                    FROM relic_upgrade_steps s1
                    JOIN relic_upgrade_steps s2 ON s2.group_id = s1.group_id
                    WHERE s1.relic_id = :rid AND s2.equivalent_grade_min <= :eq
                    ORDER BY s2.equivalent_grade_min DESC
                    """
                ),
                {"rid": rid, "eq": equivalent_grade},
            ).fetchall()
            if steps:
                candidates = [row[0] for row in steps]
            chosen_rows = []
            for cid in candidates:
                rows = conn.execute(
                    text("""
                        SELECT relic_id,target,attr,value,source,note,operation,rule_version,review_status
                        FROM relic_effect_rules
                        WHERE relic_id=:id AND calculation_status='active'
                          AND when_param IS NULL AND value_expr IS NULL AND attr<>'ignored'
                          AND NOT EXISTS (SELECT 1 FROM relic_condition_params p WHERE p.relic_id=relic_effect_rules.relic_id)
                    """),
                    {"id": cid},
                ).mappings().all()
                if rows:
                    chosen_rows = [dict(x) for x in rows]
                    break
            if not chosen_rows:
                rows = conn.execute(
                    text("""
                        SELECT relic_id,target,attr,value,source,note,operation,rule_version,review_status
                        FROM relic_effect_rules
                        WHERE relic_id=:id AND calculation_status='active'
                          AND when_param IS NULL AND value_expr IS NULL AND attr<>'ignored'
                          AND NOT EXISTS (SELECT 1 FROM relic_condition_params p WHERE p.relic_id=relic_effect_rules.relic_id)
                    """),
                    {"id": rid},
                ).mappings().all()
                chosen_rows = [dict(x) for x in rows]
            for row in chosen_rows:
                key = f"{row['relic_id']}:{row['target']}:{row['attr']}:{row['value']}"
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                effects.append(row)
        return effects


