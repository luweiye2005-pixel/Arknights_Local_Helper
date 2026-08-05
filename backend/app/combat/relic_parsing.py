"""藏品文本解析、导入补丁和敌方面板规则。"""
from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from app.combat.relic_conditions import _resolve_param_values, safe_eval_expr
from app.combat.relic_models import (
    CombatModifiers,
    EnemyStatModifiers,
    _enemy_mod_has_values,
    _mod_has_values,
)
from app.config import settings

_SIGN_NUM = r"([+\-−]?)\s*(\d+(?:\.\d+)?)"
_ENEMY = r"(?:所有)?(?:敌方单位|敌人)"


def _signed(sign: str, num: str) -> float:
    v = float(num)
    if sign in ("-", "−"):
        return -v
    return v


def parse_enemy_relic_text(name: str, usage: str) -> EnemyStatModifiers:
    """解析会影响敌人面板的藏品描述（生命/攻击/防御/攻速/法抗）。"""
    text = f"{name} {usage}"
    mod = EnemyStatModifiers()

    def _blank(m: re.Match[str]) -> str:
        return " " * (m.end() - m.start())

    # 情境句先挖掉，避免当成常驻
    text = re.sub(r"处于[^，。；\n]{0,24}(?:时|中)的?敌人[^。；\n]{0,40}", " ", text)

    # 复合：攻击力、防御力、生命+40% —— 先吃掉，避免后续单项重复
    for m in list(
        re.finditer(
            rf"{_ENEMY}的?(?:攻击力|攻击)[、,，](?:防御力|防御)[、,，](?:生命值|生命)\s*{_SIGN_NUM}\s*%",
            text,
        )
    ):
        pct = _signed(m.group(1), m.group(2)) / 100.0
        mod.atk_pct += pct
        mod.def_pct += pct
        mod.hp_pct += pct
        mod.notes.append(f"敌人攻防血{pct:+.0%}")
        text = text[: m.start()] + _blank(m) + text[m.end() :]

    for m in re.finditer(rf"{_ENEMY}的?(?:生命值|生命上限|生命)\s*{_SIGN_NUM}\s*%", text):
        pct = _signed(m.group(1), m.group(2)) / 100.0
        mod.hp_pct += pct
        mod.notes.append(f"敌人生命{pct:+.0%}")

    for m in re.finditer(rf"{_ENEMY}的?(?:攻击力|攻击)\s*{_SIGN_NUM}\s*%", text):
        pct = _signed(m.group(1), m.group(2)) / 100.0
        mod.atk_pct += pct
        mod.notes.append(f"敌人攻击{pct:+.0%}")

    for m in re.finditer(rf"{_ENEMY}的?(?:防御力|防御)\s*{_SIGN_NUM}\s*%", text):
        pct = _signed(m.group(1), m.group(2)) / 100.0
        mod.def_pct += pct
        mod.notes.append(f"敌人防御{pct:+.0%}")

    for m in re.finditer(rf"{_ENEMY}的?(?:攻击速度|攻速)\s*{_SIGN_NUM}(?!\s*%)", text):
        val = _signed(m.group(1), m.group(2))
        mod.aspd += val
        mod.notes.append(f"敌人攻速{val:+.0f}")

    for m in re.finditer(rf"{_ENEMY}的?(?:法术抗性|法抗)\s*{_SIGN_NUM}", text):
        val = _signed(m.group(1), m.group(2))
        if m.end() < len(text) and text[m.end() : m.end() + 1] == "%":
            continue
        mod.res_flat += val
        mod.notes.append(f"敌人法抗{val:+.0f}")

    return mod


def enemy_modifiers_from_effect_rows(rows: list[dict[str, Any]]) -> EnemyStatModifiers:
    mod = EnemyStatModifiers()
    for row in rows:
        if (row.get("target") or "") != "enemy":
            continue
        attr = row.get("attr") or ""
        val = float(row.get("value") or 0)
        if attr == "hp_pct":
            mod.hp_pct += val
        elif attr == "atk_pct":
            mod.atk_pct += val
        elif attr == "def_pct":
            mod.def_pct += val
        elif attr == "aspd":
            mod.aspd += val
        elif attr == "res_flat":
            mod.res_flat += val
        if row.get("note"):
            mod.notes.append(str(row["note"]))
    return mod


def normalize_damage_amps(mod: CombatModifiers) -> CombatModifiers:
    """避免「物理/法术伤害+X%」同时落入 damage_pct 与类型字段导致双计。"""
    if mod.phys_damage_pct and abs(mod.damage_pct - mod.phys_damage_pct) < 1e-9:
        mod.damage_pct = 0.0
    if mod.arts_damage_pct and abs(mod.damage_pct - mod.arts_damage_pct) < 1e-9:
        mod.damage_pct = 0.0
    return mod



def _fill_mod_gaps(base: CombatModifiers, extra: CombatModifiers) -> CombatModifiers:
    """DB 有部分效果时，用文本解析补齐缺失字段（避免漏算生命/防御等）。"""
    return CombatModifiers(
        atk_pct=base.atk_pct or extra.atk_pct,
        atk_flat=base.atk_flat or extra.atk_flat,
        def_flat=base.def_flat or extra.def_flat,
        damage_pct=base.damage_pct or extra.damage_pct,
        aspd=base.aspd or extra.aspd,
        ignore_def_pct=base.ignore_def_pct or extra.ignore_def_pct,
        true_damage=base.true_damage or extra.true_damage,
        phys_damage_pct=base.phys_damage_pct or extra.phys_damage_pct,
        arts_damage_pct=base.arts_damage_pct or extra.arts_damage_pct,
        hp_pct=base.hp_pct or extra.hp_pct,
        def_pct=base.def_pct or extra.def_pct,
        res_pct=base.res_pct or extra.res_pct,
        res_flat=base.res_flat or extra.res_flat,
        notes=base.notes + [n for n in extra.notes if n not in base.notes],
    )


def _fill_enemy_mod_gaps(base: EnemyStatModifiers, extra: EnemyStatModifiers) -> EnemyStatModifiers:
    return EnemyStatModifiers(
        hp_pct=base.hp_pct or extra.hp_pct,
        atk_pct=base.atk_pct or extra.atk_pct,
        def_pct=base.def_pct or extra.def_pct,
        aspd=base.aspd or extra.aspd,
        res_flat=base.res_flat or extra.res_flat,
        notes=base.notes + [n for n in extra.notes if n not in base.notes],
    )


def build_enemy_relic_modifiers(
    *,
    relic_ids: list[str] | None = None,
    equivalent_grade: int = 0,
    relic_conditions: dict[str, dict[str, Any]] | None = None,
    operator: dict[str, Any] | None = None,
) -> EnemyStatModifiers:
    """合并藏品对敌人面板的修正：逐件读 DB，并用文本解析补齐。"""
    from app.data import db as gdb

    ids = [i for i in (relic_ids or []) if i]
    total = EnemyStatModifiers()
    if not ids:
        return total

    schemas = gdb.get_relic_condition_schemas()
    for rid in ids:
        # MySQL is an optional enrichment source for panel calculation.  Keep the
        # calculator usable with local gamedata (and unit-testable) when the
        # database is unavailable or not configured yet.
        try:
            resolved = gdb.resolve_relic_for_grade(rid, equivalent_grade) or gdb.get_relic_row(rid)
        except Exception as e:
            raise RuntimeError(f"MySQL 藏品规则不可用: {rid}: {e}") from e
        if not resolved:
            continue
        resolved_id = resolved.get("id") or rid
        name = resolved.get("name") or resolved_id
        usage = resolved.get("usage") or resolved.get("usage_text") or ""
        piece = EnemyStatModifiers()
        schema = schemas.get(rid) or schemas.get(resolved_id) or {}
        params = _resolve_param_values(schema, (relic_conditions or {}).get(rid), operator=operator)
        try:
            rows = gdb.get_relic_rule_rows([rid], equivalent_grade)
        except Exception as e:
            raise RuntimeError(f"MySQL 敌人藏品规则不可用: {resolved_id}: {e}") from e
        for row in rows:
            if row.get("target") != "enemy" or row.get("calculation_status") != "active":
                continue
            when = row.get("when_param")
            if when and not params.get(when):
                continue
            value = float(row.get("value") or 0)
            if row.get("value_expr"):
                value = safe_eval_expr(str(row["value_expr"]), params)
            attr = row.get("attr")
            if attr in {"hp_pct", "atk_pct", "def_pct", "aspd", "res_flat"}:
                setattr(piece, attr, getattr(piece, attr) + value)
                piece.notes.append(str(row.get("note") or name))
        if _enemy_mod_has_values(piece):
            total = total.merge(piece)
            total.notes.append(f"应用遗物(敌):{name}")
    return total


def load_relic_patches() -> dict[str, dict]:
    path = settings.relic_patch_path
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"遗物补丁读取失败: {e}")
        return {}


def parse_relic_text(name: str, usage: str) -> CombatModifiers:
    """从中文描述启发式解析常见加成（导入期 / 运行时回退）。"""
    text = f"{name} {usage}"
    mod = CombatModifiers()

    def _blank(m: re.Match[str]) -> str:
        return " " * (m.end() - m.start())

    # 挖掉情境/概率句，降低误解析常驻面板
    text = re.sub(
        r"(?:每次攻击时|攻击时|部署后|技能期间|持有时若|若当前|当[^，。]{0,12}时)[^。；\n]{0,48}",
        " ",
        text,
    )
    text = re.sub(r"处于[^，。；\n]{0,24}(?:时|中)[^。；\n]{0,40}", " ", text)
    ally = r"(?:所有)?(?:我方单位|干员|友方单位)"

    # 复合：攻击力和防御力+35%
    for m in list(
        re.finditer(
            rf"(?:{ally}的?)?(?:攻击力|攻击)和(?:防御力|防御)[^%]{{0,6}}(?:提升|增加|\+|加)\s*(\d+(?:\.\d+)?)\s*%",
            text,
        )
    ):
        pct = float(m.group(1)) / 100.0
        mod.atk_pct += pct
        mod.def_pct += pct
        mod.notes.append(f"解析攻防%+{m.group(1)}%")
        text = text[: m.start()] + _blank(m) + text[m.end() :]

    for m in re.finditer(
        rf"(?:{ally}的?)?(?:攻击力|攻击)[^%]{{0,8}}(?:提升|增加|\+|加)\s*(\d+(?:\.\d+)?)\s*%",
        text,
    ):
        start = max(0, m.start() - 6)
        if "敌人" in text[start : m.start()] or "敌方" in text[start : m.start()]:
            continue
        mod.atk_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析ATK%+{m.group(1)}%")

    for m in re.finditer(
        rf"(?:{ally}的?)?(?:最大生命|生命值|生命)[^%]{{0,8}}(?:提升|增加|\+|加)\s*(\d+(?:\.\d+)?)\s*%",
        text,
    ):
        start = max(0, m.start() - 6)
        if "敌人" in text[start : m.start()] or "敌方" in text[start : m.start()]:
            continue
        mod.hp_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析HP%+{m.group(1)}%")

    for m in re.finditer(
        rf"(?:{ally}的?)?(?:防御力|防御)[^%]{{0,8}}(?:提升|增加|\+|加)\s*(\d+(?:\.\d+)?)\s*%",
        text,
    ):
        start = max(0, m.start() - 6)
        if "敌人" in text[start : m.start()] or "敌方" in text[start : m.start()]:
            continue
        mod.def_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析DEF%+{m.group(1)}%")

    for m in re.finditer(r"(?:造成的?伤害|伤害)[^%]{0,8}(?:提升|增加|\+)\s*(\d+(?:\.\d+)?)\s*%", text):
        span = text[max(0, m.start() - 4) : m.end()]
        if "物理伤害" in span or "法术伤害" in span:
            continue
        start = max(0, m.start() - 6)
        if "敌人" in text[start : m.start()] or "敌方" in text[start : m.start()]:
            continue
        mod.damage_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析伤害%+{m.group(1)}%")

    for m in re.finditer(
        rf"(?:{ally}的?)?(?:攻击速度|攻速)[^%]{{0,6}}(?:提升|增加|\+)\s*(\d+(?:\.\d+)?)",
        text,
    ):
        start = max(0, m.start() - 6)
        if "敌人" in text[start : m.start()] or "敌方" in text[start : m.start()]:
            continue
        mod.aspd += float(m.group(1))
        mod.notes.append(f"解析攻速+{m.group(1)}")

    # 干员侧减益（负百分比 / 负攻速）
    for m in re.finditer(r"(?:攻击力|攻击)[^%]{0,8}-\s*(\d+(?:\.\d+)?)\s*%", text):
        start = max(0, m.start() - 6)
        prefix = text[start : m.start()]
        if "敌人" in prefix or "敌方" in prefix:
            continue
        mod.atk_pct -= float(m.group(1)) / 100.0
        mod.notes.append(f"解析ATK%-{m.group(1)}%")

    for m in re.finditer(r"(?:最大生命|生命值|生命)[^%]{0,8}-\s*(\d+(?:\.\d+)?)\s*%", text):
        start = max(0, m.start() - 6)
        prefix = text[start : m.start()]
        if "敌人" in prefix or "敌方" in prefix:
            continue
        mod.hp_pct -= float(m.group(1)) / 100.0
        mod.notes.append(f"解析HP%-{m.group(1)}%")

    for m in re.finditer(r"(?:防御力|防御)[^%]{0,8}-\s*(\d+(?:\.\d+)?)\s*%", text):
        start = max(0, m.start() - 6)
        prefix = text[start : m.start()]
        if "敌人" in prefix or "敌方" in prefix:
            continue
        mod.def_pct -= float(m.group(1)) / 100.0
        mod.notes.append(f"解析DEF%-{m.group(1)}%")

    for m in re.finditer(r"(?:攻击速度|攻速)[^0-9+\-]{0,6}-\s*(\d+(?:\.\d+)?)", text):
        start = max(0, m.start() - 6)
        prefix = text[start : m.start()]
        if "敌人" in prefix or "敌方" in prefix:
            continue
        mod.aspd -= float(m.group(1))
        mod.notes.append(f"解析攻速-{m.group(1)}")

    for m in re.finditer(r"(?:无视|忽略)[^%]{0,6}(?:防御|防御力)\s*(\d+(?:\.\d+)?)\s*%", text):
        mod.ignore_def_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析无视防御{m.group(1)}%")

    if re.search(r"(?:攻击|造成|变为|附带)[^。；\n]{0,12}(?:真实伤害|真伤)", text) and "受到真实伤害" not in text:
        mod.true_damage = True
        mod.notes.append("解析真伤")

    for m in re.finditer(r"物理伤害[^%]{0,8}(?:提升|增加|\+)\s*(\d+(?:\.\d+)?)\s*%", text):
        mod.phys_damage_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析物理伤害%+{m.group(1)}%")

    for m in re.finditer(r"法术伤害[^%]{0,8}(?:提升|增加|\+)\s*(\d+(?:\.\d+)?)\s*%", text):
        mod.arts_damage_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析法术伤害%+{m.group(1)}%")

    return mod


def modifiers_from_patch(patch: dict) -> CombatModifiers:
    return CombatModifiers(
        atk_pct=float(patch.get("atk_pct") or 0),
        atk_flat=float(patch.get("atk_flat") or 0),
        damage_pct=float(patch.get("damage_pct") or 0),
        aspd=float(patch.get("aspd") or 0),
        ignore_def_pct=float(patch.get("ignore_def_pct") or 0),
        true_damage=bool(patch.get("true_damage") or False),
        phys_damage_pct=float(patch.get("phys_damage_pct") or 0),
        arts_damage_pct=float(patch.get("arts_damage_pct") or 0),
        hp_pct=float(patch.get("hp_pct") or 0),
        def_pct=float(patch.get("def_pct") or 0),
        notes=[f"补丁:{patch.get('note') or 'manual'}"] if patch else [],
    )


def modifiers_from_effect_rows(rows: list[dict[str, Any]]) -> CombatModifiers:
    mod = CombatModifiers()
    for row in rows:
        if (row.get("target") or "operator") != "operator":
            continue
        attr = row.get("attr") or ""
        val = float(row.get("value") or 0)
        if attr == "atk_pct":
            mod.atk_pct += val
        elif attr == "atk_flat":
            mod.atk_flat += val
        elif attr == "damage_pct":
            mod.damage_pct += val
        elif attr == "aspd":
            mod.aspd += val
        elif attr == "ignore_def_pct":
            mod.ignore_def_pct = min(1.0, mod.ignore_def_pct + val)
        elif attr == "true_damage":
            mod.true_damage = mod.true_damage or bool(val)
        elif attr == "phys_damage_pct":
            mod.phys_damage_pct += val
        elif attr == "arts_damage_pct":
            mod.arts_damage_pct += val
        elif attr == "hp_pct":
            mod.hp_pct += val
        elif attr == "def_pct":
            mod.def_pct += val
        elif attr == "def_flat":
            mod.def_flat += val
        elif attr == "res_pct":
            mod.res_pct += val
        elif attr == "res_flat":
            mod.res_flat += val
        if row.get("note"):
            mod.notes.append(str(row["note"]))
    return mod

