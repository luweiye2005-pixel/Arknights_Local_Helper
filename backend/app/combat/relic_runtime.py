"""结构化藏品规则的运行时合并。"""
from __future__ import annotations

from typing import Any

from app.combat.relic_conditions import load_relic_conditions
from app.combat.relic_models import CombatModifiers, _mod_has_values
from app.combat.relic_parsing import normalize_damage_amps, modifiers_from_effect_rows

def _strip_operator_panel_attrs(mod: CombatModifiers) -> CombatModifiers:
    """去掉由条件补丁接管的干员面板字段，避免与条件效果重复叠加。"""
    return CombatModifiers(
        atk_pct=0.0,
        atk_flat=0.0,
        def_flat=0.0,
        damage_pct=mod.damage_pct,
        aspd=0.0,
        ignore_def_pct=mod.ignore_def_pct,
        true_damage=mod.true_damage,
        phys_damage_pct=mod.phys_damage_pct,
        arts_damage_pct=mod.arts_damage_pct,
        hp_pct=0.0,
        def_pct=0.0,
        res_pct=0.0,
        res_flat=0.0,
        notes=list(mod.notes) + ["条件藏品:已剥离常驻面板"],
    )


def _condition_schema_for(rid: str, resolved_id: str | None = None) -> dict | None:
    schemas = load_relic_conditions()
    return schemas.get(rid) or (schemas.get(resolved_id) if resolved_id else None)


def build_relic_modifiers(
    relics: list[dict[str, Any]] | None = None,
    *,
    relic_ids: list[str] | None = None,
    equivalent_grade: int = 0,
) -> CombatModifiers:
    """合并多个遗物的修正：逐件优先 MySQL effects，缺失则文本/补丁解析。"""
    from app.data import db as gdb

    ids = relic_ids or [r.get("id") for r in (relics or []) if r.get("id")]
    ids = [i for i in ids if i]
    total = CombatModifiers()

    if not ids:
        return total

    for rid in ids:
        # The structured database improves accuracy but is not required for
        # offline/local calculation; fall back to the supplied relic text.
        try:
            resolved = gdb.resolve_relic_for_grade(rid, equivalent_grade) or gdb.get_relic_row(rid)
        except Exception as e:
            raise RuntimeError(f"MySQL 藏品规则不可用: {rid}: {e}") from e
        from_list = next((r for r in (relics or []) if r.get("id") == rid), None)
        name = (resolved or {}).get("name") or (from_list or {}).get("name") or rid
        usage = (resolved or {}).get("usage") or (from_list or {}).get("usage") or ""
        resolved_id = (resolved or {}).get("id") or rid
        schema = _condition_schema_for(rid, resolved_id)
        if schema and schema.get("replace_operator_panel", True):
            # 面板数值改由条件补丁计算；保留伤害类等非面板解析（如有）
            piece = CombatModifiers()
            try:
                rows = gdb.get_relic_effects_merged([rid], equivalent_grade=equivalent_grade)
                piece = _strip_operator_panel_attrs(modifiers_from_effect_rows(rows))
            except Exception as e:
                raise RuntimeError(f"MySQL 藏品规则不可用: {rid}: {e}") from e
            piece = normalize_damage_amps(piece)
            if not any(
                [
                    abs(piece.damage_pct) > 1e-12,
                    piece.ignore_def_pct,
                    piece.true_damage,
                    abs(piece.phys_damage_pct) > 1e-12,
                    abs(piece.arts_damage_pct) > 1e-12,
                ]
            ):
                total.notes.append(f"条件藏品(面板见条件控件):{name}")
                continue
            total = total.merge(piece)
            total.notes.append(f"条件藏品(保留非面板效果):{name}")
            continue

        piece = CombatModifiers()
        try:
            rows = gdb.get_relic_effects_merged([rid], equivalent_grade=equivalent_grade)
            piece = modifiers_from_effect_rows(rows)
        except Exception as e:
            raise RuntimeError(f"MySQL 藏品规则不可用: {rid}: {e}") from e

        piece = normalize_damage_amps(piece)
        if _mod_has_values(piece):
            total = total.merge(piece)
            total.notes.append(f"应用遗物:{name}")
        else:
            total.notes.append(f"无面板数值效果:{name}")
    return total

