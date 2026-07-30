"""遗物 modifier：优先读 MySQL relic_effects，兼容旧补丁接口。"""
from __future__ import annotations

import ast
import json
import math
import operator
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from loguru import logger

from app.config import settings


@dataclass
class CombatModifiers:
    """可叠加的战斗修正。"""

    atk_pct: float = 0.0
    atk_flat: float = 0.0
    damage_pct: float = 0.0
    aspd: float = 0.0
    ignore_def_pct: float = 0.0
    true_damage: bool = False
    phys_damage_pct: float = 0.0
    arts_damage_pct: float = 0.0
    hp_pct: float = 0.0
    def_pct: float = 0.0
    notes: list[str] = field(default_factory=list)

    def merge(self, other: "CombatModifiers") -> "CombatModifiers":
        return CombatModifiers(
            atk_pct=self.atk_pct + other.atk_pct,
            atk_flat=self.atk_flat + other.atk_flat,
            damage_pct=self.damage_pct + other.damage_pct,
            aspd=self.aspd + other.aspd,
            ignore_def_pct=min(1.0, self.ignore_def_pct + other.ignore_def_pct),
            true_damage=self.true_damage or other.true_damage,
            phys_damage_pct=self.phys_damage_pct + other.phys_damage_pct,
            arts_damage_pct=self.arts_damage_pct + other.arts_damage_pct,
            hp_pct=self.hp_pct + other.hp_pct,
            def_pct=self.def_pct + other.def_pct,
            notes=self.notes + other.notes,
        )

    def to_dict(self) -> dict:
        return asdict(self)


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
    path = settings.relic_conditions_path
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if not str(k).startswith("_") and isinstance(v, dict)}
    except Exception as e:
        logger.warning(f"条件藏品补丁读取失败: {e}")
        return {}


def load_outer_buffs() -> dict[str, dict]:
    path = settings.outer_buffs_path
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if not str(k).startswith("_") and isinstance(v, dict)}
    except Exception as e:
        logger.warning(f"局外加成补丁读取失败: {e}")
        return {}


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
        elif pid == "applies" and p.get("auto") and operator is not None:
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


@dataclass
class EnemyStatModifiers:
    """藏品对敌人面板的数值修正。"""

    hp_pct: float = 0.0
    atk_pct: float = 0.0
    def_pct: float = 0.0
    aspd: float = 0.0
    res_flat: float = 0.0
    notes: list[str] = field(default_factory=list)

    def merge(self, other: "EnemyStatModifiers") -> "EnemyStatModifiers":
        return EnemyStatModifiers(
            hp_pct=self.hp_pct + other.hp_pct,
            atk_pct=self.atk_pct + other.atk_pct,
            def_pct=self.def_pct + other.def_pct,
            aspd=self.aspd + other.aspd,
            res_flat=self.res_flat + other.res_flat,
            notes=self.notes + other.notes,
        )

    def to_dict(self) -> dict:
        return asdict(self)


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

    # 复合：攻击力、防御力、生命+40% —— 先吃掉，避免后续单项重复
    def _blank(m: re.Match[str]) -> str:
        return " " * (m.end() - m.start())

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


def _normalize_damage_amps(mod: CombatModifiers) -> CombatModifiers:
    """避免「物理/法术伤害+X%」同时落入 damage_pct 与类型字段导致双计。"""
    if mod.phys_damage_pct and abs(mod.damage_pct - mod.phys_damage_pct) < 1e-9:
        mod.damage_pct = 0.0
    if mod.arts_damage_pct and abs(mod.damage_pct - mod.arts_damage_pct) < 1e-9:
        mod.damage_pct = 0.0
    return mod


def _mod_has_values(mod: CombatModifiers) -> bool:
    return any(
        [
            abs(mod.atk_pct) > 1e-12,
            abs(mod.atk_flat) > 1e-12,
            abs(mod.damage_pct) > 1e-12,
            abs(mod.aspd) > 1e-12,
            abs(mod.ignore_def_pct) > 1e-12,
            mod.true_damage,
            abs(mod.phys_damage_pct) > 1e-12,
            abs(mod.arts_damage_pct) > 1e-12,
            abs(mod.hp_pct) > 1e-12,
            abs(mod.def_pct) > 1e-12,
        ]
    )


def _enemy_mod_has_values(mod: EnemyStatModifiers) -> bool:
    return any([mod.hp_pct, mod.atk_pct, mod.def_pct, mod.aspd, mod.res_flat])


def _fill_mod_gaps(base: CombatModifiers, extra: CombatModifiers) -> CombatModifiers:
    """DB 有部分效果时，用文本解析补齐缺失字段（避免漏算生命/防御等）。"""
    return CombatModifiers(
        atk_pct=base.atk_pct or extra.atk_pct,
        atk_flat=base.atk_flat or extra.atk_flat,
        damage_pct=base.damage_pct or extra.damage_pct,
        aspd=base.aspd or extra.aspd,
        ignore_def_pct=base.ignore_def_pct or extra.ignore_def_pct,
        true_damage=base.true_damage or extra.true_damage,
        phys_damage_pct=base.phys_damage_pct or extra.phys_damage_pct,
        arts_damage_pct=base.arts_damage_pct or extra.arts_damage_pct,
        hp_pct=base.hp_pct or extra.hp_pct,
        def_pct=base.def_pct or extra.def_pct,
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
) -> EnemyStatModifiers:
    """合并藏品对敌人面板的修正：逐件读 DB，并用文本解析补齐。"""
    from app.data import db as gdb

    ids = [i for i in (relic_ids or []) if i]
    total = EnemyStatModifiers()
    if not ids:
        return total

    for rid in ids:
        resolved = gdb.resolve_relic_for_grade(rid, equivalent_grade) or gdb.get_relic_row(rid)
        if not resolved:
            continue
        resolved_id = resolved.get("id") or rid
        name = resolved.get("name") or resolved_id
        usage = resolved.get("usage") or resolved.get("usage_text") or ""
        piece = EnemyStatModifiers()
        try:
            rows = gdb.get_relic_effects_merged([rid], equivalent_grade=equivalent_grade)
            piece = enemy_modifiers_from_effect_rows(rows)
        except Exception as e:
            logger.warning(f"读敌人藏品效果失败 {resolved_id}: {e}")
        text_piece = parse_enemy_relic_text(name, usage)
        piece = _fill_enemy_mod_gaps(piece, text_piece)
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

    # 复合：攻击力和防御力+35%
    for m in re.finditer(
        r"(?:攻击力|攻击)和(?:防御力|防御)[^%]{0,6}(?:提升|增加|\+|加)\s*(\d+(?:\.\d+)?)\s*%",
        text,
    ):
        pct = float(m.group(1)) / 100.0
        mod.atk_pct += pct
        mod.def_pct += pct
        mod.notes.append(f"解析攻防%+{m.group(1)}%")
        text = text[: m.start()] + (" " * (m.end() - m.start())) + text[m.end() :]

    for m in re.finditer(r"(?:攻击力|攻击)[^%]{0,8}(?:提升|增加|\+|加)\s*(\d+(?:\.\d+)?)\s*%", text):
        mod.atk_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析ATK%+{m.group(1)}%")

    for m in re.finditer(r"(?:最大生命|生命值|生命)[^%]{0,8}(?:提升|增加|\+|加)\s*(\d+(?:\.\d+)?)\s*%", text):
        start = max(0, m.start() - 4)
        prefix = text[start : m.start()]
        if "敌人" in prefix or "敌方" in prefix:
            continue
        mod.hp_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析HP%+{m.group(1)}%")

    for m in re.finditer(r"(?:防御力|防御)[^%]{0,8}(?:提升|增加|\+|加)\s*(\d+(?:\.\d+)?)\s*%", text):
        start = max(0, m.start() - 4)
        prefix = text[start : m.start()]
        if "敌人" in prefix or "敌方" in prefix:
            continue
        mod.def_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析DEF%+{m.group(1)}%")

    for m in re.finditer(r"(?:造成的?伤害|伤害)[^%]{0,8}(?:提升|增加|\+)\s*(\d+(?:\.\d+)?)\s*%", text):
        # 「物理伤害/法术伤害」由下方专项解析，避免重复计入 damage_pct
        span = text[max(0, m.start() - 4) : m.end()]
        if "物理伤害" in span or "法术伤害" in span:
            continue
        mod.damage_pct += float(m.group(1)) / 100.0
        mod.notes.append(f"解析伤害%+{m.group(1)}%")

    for m in re.finditer(r"(?:攻击速度|攻速)[^%]{0,6}(?:提升|增加|\+)\s*(\d+(?:\.\d+)?)", text):
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

    if "真实伤害" in text or "真伤" in text:
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
        if row.get("note"):
            mod.notes.append(str(row["note"]))
    return mod


def _strip_operator_panel_attrs(mod: CombatModifiers) -> CombatModifiers:
    """去掉由条件补丁接管的干员面板字段，避免与条件效果重复叠加。"""
    return CombatModifiers(
        atk_pct=0.0,
        atk_flat=0.0,
        damage_pct=mod.damage_pct,
        aspd=0.0,
        ignore_def_pct=mod.ignore_def_pct,
        true_damage=mod.true_damage,
        phys_damage_pct=mod.phys_damage_pct,
        arts_damage_pct=mod.arts_damage_pct,
        hp_pct=0.0,
        def_pct=0.0,
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
    patches = load_relic_patches()
    total = CombatModifiers()

    if not ids:
        for r in relics or []:
            rid = r.get("id") or ""
            schema = _condition_schema_for(rid)
            if schema and schema.get("replace_operator_panel", True):
                total.notes.append(f"条件藏品跳过常驻面板:{r.get('name') or rid}")
                continue
            if rid in patches:
                total = total.merge(_normalize_damage_amps(modifiers_from_patch(patches[rid])))
            else:
                total = total.merge(
                    _normalize_damage_amps(parse_relic_text(r.get("name") or "", r.get("usage") or ""))
                )
            total.notes.append(f"应用遗物:{r.get('name') or rid}")
        return total

    for rid in ids:
        resolved = gdb.resolve_relic_for_grade(rid, equivalent_grade) or gdb.get_relic_row(rid)
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
                logger.warning(f"从 MySQL 读 relic_effects 失败 {rid}: {e}")
            if usage:
                piece = _fill_mod_gaps(piece, parse_relic_text(name, usage))
            piece = _normalize_damage_amps(piece)
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
            logger.warning(f"从 MySQL 读 relic_effects 失败 {rid}: {e}")

        if not _mod_has_values(piece):
            if rid in patches:
                piece = modifiers_from_patch(patches[rid])
            elif resolved_id in patches:
                piece = modifiers_from_patch(patches[resolved_id])
            else:
                piece = parse_relic_text(name, usage)
        else:
            # DB 可能只有部分字段（旧导入），用当前文本解析补齐生命/防御等
            piece = _fill_mod_gaps(piece, parse_relic_text(name, usage))

        piece = _normalize_damage_amps(piece)
        if _mod_has_values(piece):
            total = total.merge(piece)
            total.notes.append(f"应用遗物:{name}")
        else:
            total.notes.append(f"无面板数值效果:{name}")
    return total
