"""藏品条件表达式、自动适用规则与贡献明细。"""
from __future__ import annotations

import ast
import math
import operator
from typing import Any

from loguru import logger

from app.combat.relic_models import CombatModifiers, _mod_has_values

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_ALLOWED_FUNCS = {
    "floor": math.floor,
    "ceil": math.ceil,
    "max": max,
    "min": min,
}


def safe_eval_expr(expr: str, variables: dict[str, float]) -> float:
    """安全求值：仅允许数字、参数名、floor/ceil 与四则运算。"""
    tree = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise ValueError(f"未知变量: {node.id}")
            return float(variables[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return float(_BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return float(_UNARY_OPS[type(node.op)](_eval(node.operand)))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise ValueError("不允许的函数")
            if node.keywords:
                raise ValueError("不允许关键字参数")
            args = [_eval(a) for a in node.args]
            return float(_ALLOWED_FUNCS[node.func.id](*args))
        raise ValueError(f"不支持的表达式节点: {type(node).__name__}")

    return float(_eval(tree))


def load_relic_conditions() -> dict[str, dict]:
    from app.data import db as gdb
    return gdb.get_relic_condition_schemas()


def load_outer_buffs() -> dict[str, dict]:
    from app.data import db as gdb
    return gdb.get_theme_outer_buffs()


def list_condition_schemas(theme_id: str | None = None) -> dict[str, dict]:
    """返回条件 schema；可选按主题前缀过滤。"""
    all_c = load_relic_conditions()
    if not theme_id:
        return all_c
    prefix = f"{theme_id}_"
    return {k: v for k, v in all_c.items() if k.startswith(prefix)}


def get_outer_buff(theme_id: str | None) -> dict[str, Any] | None:
    if not theme_id:
        return None
    return load_outer_buffs().get(theme_id)


def match_applies_auto(auto: dict[str, Any] | None, operator: dict[str, Any] | None) -> bool:
    """按补丁 auto 规则判断当前干员是否匹配 applies。"""
    if not auto:
        return True
    if not operator:
        return True
    if "position" in auto:
        want = str(auto["position"] or "").upper()
        have = str(operator.get("position") or "").upper()
        if want and have != want:
            return False
    if "profession" in auto:
        allowed = [str(x) for x in (auto["profession"] or [])]
        if allowed:
            from app.data.store import PROFESSION_CN

            p = str(operator.get("profession") or "")
            pcn = str(operator.get("profession_cn") or "") or PROFESSION_CN.get(p, "")
            ok = False
            for a in allowed:
                au = a.upper()
                if au == p.upper() or a == pcn or PROFESSION_CN.get(p, "") == a:
                    ok = True
                    break
                # 别名：术士→术师
                if a in {"术士", "术师"} and pcn in {"术士", "术师"}:
                    ok = True
                    break
            if not ok:
                return False
    if "sub_profession_cn_any" in auto:
        names = [str(x) for x in (auto["sub_profession_cn_any"] or [])]
        if names:
            scn = str(operator.get("sub_profession_cn") or "")
            if scn not in names:
                return False
    return True


def _resolve_param_values(
    schema: dict,
    user_vals: dict[str, Any] | None,
    operator: dict[str, Any] | None = None,
) -> dict[str, float]:
    user_vals = user_vals or {}
    out: dict[str, float] = {}
    for p in schema.get("params") or []:
        pid = p.get("id")
        if not pid:
            continue
        ptype = p.get("type") or "number"
        if pid in user_vals:
            raw = user_vals[pid]
        elif p.get("auto") and operator is not None:
            raw = match_applies_auto(p.get("auto"), operator)
        else:
            raw = p.get("default", 0)
        if ptype == "toggle":
            out[pid] = 1.0 if bool(raw) else 0.0
        else:
            try:
                val = float(raw)
            except (TypeError, ValueError):
                val = float(p.get("default") or 0)
            if p.get("min") is not None:
                val = max(float(p["min"]), val)
            if p.get("max") is not None:
                val = min(float(p["max"]), val)
            out[pid] = val
    return out


def _apply_attr_to_mod(mod: CombatModifiers, attr: str, value: float) -> None:
    if attr == "atk_pct":
        mod.atk_pct += value
    elif attr == "atk_flat":
        mod.atk_flat += value
    elif attr == "hp_pct":
        mod.hp_pct += value
    elif attr == "def_pct":
        mod.def_pct += value
    elif attr == "def_flat":
        mod.def_flat += value
    elif attr == "res_pct":
        mod.res_pct += value
    elif attr == "res_flat":
        mod.res_flat += value
    elif attr == "aspd":
        mod.aspd += value
    elif attr == "damage_pct":
        mod.damage_pct += value
    elif attr == "phys_damage_pct":
        mod.phys_damage_pct += value
    elif attr == "arts_damage_pct":
        mod.arts_damage_pct += value
    elif attr == "ignore_def_pct":
        mod.ignore_def_pct = min(1.0, mod.ignore_def_pct + value)
    elif attr == "true_damage":
        mod.true_damage = mod.true_damage or bool(value)


def build_conditional_relic_modifiers(
    relic_ids: list[str] | None,
    relic_conditions: dict[str, dict[str, Any]] | None = None,
    operator: dict[str, Any] | None = None,
) -> CombatModifiers:
    """按补丁与用户条件参数计算额外干员修正。"""
    ids = [i for i in (relic_ids or []) if i]
    schemas = load_relic_conditions()
    total = CombatModifiers()
    if not ids:
        return total

    for rid in ids:
        schema = schemas.get(rid)
        if not schema:
            continue
        params = _resolve_param_values(schema, (relic_conditions or {}).get(rid), operator=operator)
        piece = CombatModifiers()
        for eff in schema.get("operator_effects") or []:
            when = eff.get("when")
            if when:
                if not params.get(when):
                    continue
            attr = eff.get("attr") or ""
            if not attr:
                continue
            if "expr" in eff and eff["expr"]:
                try:
                    val = safe_eval_expr(str(eff["expr"]), params)
                except Exception as e:
                    logger.warning(f"条件表达式求值失败 {rid}/{eff['expr']}: {e}")
                    continue
            else:
                val = float(eff.get("value") or 0)
            _apply_attr_to_mod(piece, attr, val)
        if _mod_has_values(piece):
            name = schema.get("name") or rid
            piece.notes.append(f"条件效果:{name}")
            total = total.merge(piece)
    return total


def build_relic_contributions(
    relic_ids: list[str] | None,
    relic_conditions: dict[str, dict[str, Any]] | None = None,
    operator: dict[str, Any] | None = None,
    equivalent_grade: int = 0,
) -> dict[str, Any]:
    """Evaluate MySQL rules and retain per-relic provenance/formulas."""
    from app.data import db as gdb

    conditions = relic_conditions or {}
    schemas = gdb.get_relic_condition_schemas()
    grouped: dict[str, dict[str, Any]] = {"operator_panel": {}, "enemy_panel": {}}
    conditional: list[dict[str, Any]] = []
    damage: dict[str, list[dict[str, Any]]] = {
        "all": [], "PHYS": [], "MAGIC": [], "TRUE": [], "ELEMENTAL": []
    }
    for base_id in relic_ids or []:
        resolved = gdb.resolve_relic_for_grade(base_id, equivalent_grade) or gdb.get_relic_row(base_id) or {"id": base_id, "name": base_id}
        rid, name = resolved.get("id") or base_id, resolved.get("name") or base_id
        schema = schemas.get(base_id) or schemas.get(rid) or {}
        params = _resolve_param_values(schema, conditions.get(base_id) or conditions.get(rid), operator=operator)
        for rule in gdb.get_relic_rule_rows([base_id], equivalent_grade):
            if rule.get("calculation_status") != "active" or rule.get("attr") == "ignored":
                continue
            when = rule.get("when_param")
            if when and not params.get(when):
                continue
            value = float(rule.get("value") or 0)
            expr = rule.get("value_expr")
            if expr:
                try:
                    value = safe_eval_expr(str(expr), params)
                except Exception:
                    continue
            item = {
                "relic_id": base_id, "resolved_id": rid, "name": name,
                "attr": rule.get("attr"), "value": value, "operation": rule.get("operation") or "add",
                "condition": ", ".join(f"{key}={val:g}" for key, val in params.items()) if params else None,
                "formula": f"{expr} = {value:g}" if expr else f"{rule.get('attr')} {value:+g}",
                "rule_version": int(rule.get("rule_version") or 1), "source": rule.get("source"),
            }
            attr, target = str(rule.get("attr") or ""), rule.get("target")
            if attr in {"damage_pct", "phys_damage_pct", "arts_damage_pct", "true_damage_pct", "elemental_damage_pct"}:
                scope = {
                    "phys_damage_pct": "PHYS", "arts_damage_pct": "MAGIC",
                    "true_damage_pct": "TRUE", "elemental_damage_pct": "ELEMENTAL",
                }.get(attr, "all")
                item["factor"] = (1.0 + value) if (rule.get("operation") or "add") == "multiply" else (1.0 + value)
                item["display"] = f"×{item['factor'] * 100:g}%"
                damage[scope].append(item)
                continue
            bucket_name = "enemy_panel" if target == "enemy" else "operator_panel"
            bucket = grouped[bucket_name].setdefault(attr, {"total": 0.0, "items": []})
            bucket["total"] += value
            item["display"] = f"{value * 100:+g}%" if attr.endswith("_pct") else f"{value:+g}"
            bucket["items"].append(item)
            if params:
                conditional.append(item)
    factors_out = {}
    for scope, items in damage.items():
        product = 1.0
        for item in items:
            product *= float(item["factor"])
        factors_out[scope] = {"product": product, "items": items, "formula": " × ".join(item["display"] for item in items) or "×100%"}
    return {**grouped, "conditional": conditional, "damage_factors": factors_out}


def outer_buff_to_modifiers(buff: dict[str, Any] | None) -> CombatModifiers:
    if not buff:
        return CombatModifiers()
    return CombatModifiers(
        atk_pct=float(buff.get("atk_pct") or 0),
        hp_pct=float(buff.get("hp_pct") or 0),
        def_pct=float(buff.get("def_pct") or 0),
        aspd=float(buff.get("aspd") or 0),
        notes=[f"局外满级:{buff.get('name') or 'outer'}"] if any(
            float(buff.get(k) or 0) for k in ("atk_pct", "hp_pct", "def_pct", "aspd")
        )
        else [],
    )


def manual_bonus_to_modifiers(manual: dict[str, Any] | None) -> CombatModifiers:
    if not manual:
        return CombatModifiers()
    return CombatModifiers(
        atk_pct=float(manual.get("atk_pct") or 0),
        hp_pct=float(manual.get("hp_pct") or 0),
        def_pct=float(manual.get("def_pct") or 0),
        aspd=float(manual.get("aspd") or 0),
        notes=["手填加成"]
        if any(float(manual.get(k) or 0) for k in ("atk_pct", "hp_pct", "def_pct", "aspd"))
        else [],
    )



