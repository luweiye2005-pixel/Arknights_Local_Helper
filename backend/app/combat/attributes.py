"""面板属性计算。"""
from __future__ import annotations

import re
from typing import Any


def interpolate_frames(frames: list[dict], level: int) -> dict[str, float]:
    """在 attributesKeyFrames 间线性插值。"""
    if not frames:
        return {"maxHp": 0, "atk": 0, "def": 0, "magicResistance": 0, "attackSpeed": 100, "baseAttackTime": 1}

    frames = sorted(frames, key=lambda f: f.get("level", 0))
    if level <= frames[0]["level"]:
        return dict(frames[0].get("data") or {})
    if level >= frames[-1]["level"]:
        return dict(frames[-1].get("data") or {})

    lo = frames[0]
    hi = frames[-1]
    for i in range(len(frames) - 1):
        if frames[i]["level"] <= level <= frames[i + 1]["level"]:
            lo, hi = frames[i], frames[i + 1]
            break

    span = hi["level"] - lo["level"]
    t = 0 if span == 0 else (level - lo["level"]) / span
    lo_d = lo.get("data") or {}
    hi_d = hi.get("data") or {}
    keys = set(lo_d) | set(hi_d)
    out: dict[str, float] = {}
    for k in keys:
        a = float(lo_d.get(k) or 0)
        b = float(hi_d.get(k) or 0)
        out[k] = a + (b - a) * t
    return out


def favor_bonus(favor_frames: list[dict], favor_percent: int) -> dict[str, float]:
    """信赖加成（0–100% 映射 favorKeyFrames 首末帧）。"""
    if not favor_frames:
        return {}
    frames = sorted(favor_frames, key=lambda f: f.get("level", 0))
    t = max(0.0, min(1.0, favor_percent / 100.0))
    lo = frames[0].get("data") or {}
    hi = frames[-1].get("data") or {}
    out = {}
    for k in set(lo) | set(hi):
        a = float(lo.get(k) or 0)
        b = float(hi.get(k) or 0)
        out[k] = a + (b - a) * t
    return out


def potential_flat_bonus(potential_ranks: list[dict[str, Any]] | None, potential: int) -> dict[str, float]:
    """按潜能档位累加 potentialRanks 中的定值加成（潜能 1→ranks[0] … 潜能 5→ranks[0..4]）。"""
    out = {"hp": 0.0, "atk": 0.0, "def": 0.0, "attack_speed": 0.0, "res": 0.0}
    ranks = potential_ranks or []
    n = max(0, min(int(potential or 0), len(ranks)))
    for i in range(n):
        row = ranks[i] or {}
        # 已归一化的行：{hp,atk,def,aspd,res}
        if any(k in row for k in ("hp", "atk", "def", "aspd", "res", "attack_speed")):
            out["hp"] += float(row.get("hp") or 0)
            out["atk"] += float(row.get("atk") or 0)
            out["def"] += float(row.get("def") or 0)
            out["attack_speed"] += float(row.get("aspd") or row.get("attack_speed") or 0)
            out["res"] += float(row.get("res") or 0)
            continue
        # 原始 potentialRanks 条目
        buff = (row.get("buff") or {}).get("attributes") or {}
        for mod in buff.get("attributeModifiers") or []:
            if not isinstance(mod, dict):
                continue
            if str(mod.get("formulaItem") or "ADDITION").upper() not in ("ADDITION", "FINAL_ADDITION"):
                continue
            at = str(mod.get("attributeType") or "").upper()
            val = float(mod.get("value") or 0)
            if at in ("MAX_HP", "HP"):
                out["hp"] += val
            elif at == "ATK":
                out["atk"] += val
            elif at == "DEF":
                out["def"] += val
            elif at in ("ATTACK_SPEED", "ATTACKSPEED"):
                out["attack_speed"] += val
            elif at in ("MAGIC_RESISTANCE", "MAGICRESISTANCE"):
                out["res"] += val
    return out


def _phase_to_elite(unlock: dict[str, Any] | None) -> int:
    if not unlock:
        return 0
    phase = str(unlock.get("phase") or "")
    if phase.endswith("2") or phase == "PHASE_2":
        return 2
    if phase.endswith("1") or phase == "PHASE_1":
        return 1
    return 0


def talent_panel_bonus(
    talents: list[dict[str, Any]] | None,
    elite: int,
    potential: int,
) -> dict[str, float]:
    """
    选取当前精英/潜能下已解锁的天赋候选，提取可常驻计入面板的属性。
    仅处理 blackboard 中的面板向 key（atk/max_hp/def/attack_speed 等）；
    条件触发类天赋无法完整模拟，有数值的也按常驻近似。
    """
    out = {"hp": 0.0, "atk": 0.0, "def": 0.0, "attack_speed": 0.0, "res": 0.0, "atk_pct": 0.0, "hp_pct": 0.0, "def_pct": 0.0}
    if not talents:
        return out

    # 按 talent_index 分组，取满足 elite/potential 的最高档候选
    by_index: dict[int, list[dict]] = {}
    for t in talents:
        idx = int(t.get("index") if t.get("index") is not None else t.get("talent_index") or 0)
        by_index.setdefault(idx, []).append(t)

    for _idx, cands in by_index.items():
        eligible: list[dict] = []
        for c in cands:
            ue = c.get("unlock_elite")
            if ue is None:
                ue = _phase_to_elite(c.get("unlock_condition") or c.get("unlockCondition"))
            pr = int(c.get("potential_rank") if c.get("potential_rank") is not None else c.get("requiredPotentialRank") or 0)
            if int(ue or 0) <= int(elite) and int(pr) <= int(potential or 0):
                eligible.append(c)
        if not eligible:
            continue
        # 优先更高精英，再更高潜能
        eligible.sort(
            key=lambda c: (
                int(c.get("unlock_elite") if c.get("unlock_elite") is not None else _phase_to_elite(c.get("unlock_condition") or c.get("unlockCondition")) or 0),
                int(c.get("potential_rank") if c.get("potential_rank") is not None else c.get("requiredPotentialRank") or 0),
            )
        )
        chosen = eligible[-1]
        bb = chosen.get("blackboard") or []
        if isinstance(bb, dict):
            items = [{"key": k, "value": v} for k, v in bb.items()]
        else:
            items = list(bb)
        for b in items:
            if not isinstance(b, dict):
                continue
            key = str(b.get("key") or "")
            try:
                val = float(b.get("value") or 0)
            except (TypeError, ValueError):
                continue
            if key in ("atk",):
                # 天赋 atk 通常为加算比例（0.1=+10%）
                if 0 < abs(val) < 5:
                    out["atk_pct"] += val
                else:
                    out["atk"] += val
            elif key in ("max_hp", "hp"):
                if 0 < abs(val) < 5:
                    out["hp_pct"] += val
                else:
                    out["hp"] += val
            elif key in ("def",):
                if 0 < abs(val) < 5:
                    out["def_pct"] += val
                else:
                    out["def"] += val
            elif key in ("attack_speed",):
                out["attack_speed"] += val
            elif key in ("magic_resistance", "magicResistance"):
                out["res"] += val
    return out


def calc_operator_panel(
    operator: dict[str, Any],
    elite: int,
    level: int,
    favor_percent: int = 100,
    potential: int = 0,
    module_atk_flat: float = 0,
    module_atk_pct: float = 0,
    module_hp_flat: float = 0,
    module_def_flat: float = 0,
    module_aspd: float = 0,
    apply_talents: bool = True,
) -> dict[str, float]:
    """计算干员面板（ATK/HP/DEF/攻速/攻击间隔）。"""
    phases = operator.get("raw_phases") or []
    if not phases:
        return {"hp": 0, "atk": 0, "def": 0, "res": 0, "attack_speed": 100, "base_attack_time": 1.0}

    elite = max(0, min(elite, len(phases) - 1))
    phase = phases[elite]
    frames = phase.get("attributesKeyFrames") or []
    base = interpolate_frames(frames, level)
    fav = favor_bonus(operator.get("favor_key_frames") or [], favor_percent)
    pot = potential_flat_bonus(operator.get("potential_ranks") or [], potential)
    tal = (
        talent_panel_bonus(operator.get("talents") or [], elite, potential)
        if apply_talents
        else {"hp": 0.0, "atk": 0.0, "def": 0.0, "attack_speed": 0.0, "res": 0.0, "atk_pct": 0.0, "hp_pct": 0.0, "def_pct": 0.0}
    )

    hp = (
        float(base.get("maxHp") or 0)
        + float(fav.get("maxHp") or 0)
        + pot["hp"]
        + tal["hp"]
        + float(module_hp_flat or 0)
    )
    defense = (
        float(base.get("def") or 0)
        + float(fav.get("def") or 0)
        + pot["def"]
        + tal["def"]
        + float(module_def_flat or 0)
    )
    atk = (
        float(base.get("atk") or 0)
        + float(fav.get("atk") or 0)
        + pot["atk"]
        + tal["atk"]
    )
    # 模组 ATK% 与天赋 ATK% 加算后再加模组定值
    atk = atk * (1.0 + float(module_atk_pct or 0) + float(tal.get("atk_pct") or 0)) + float(module_atk_flat or 0)
    hp = hp * (1.0 + float(tal.get("hp_pct") or 0))
    defense = defense * (1.0 + float(tal.get("def_pct") or 0))

    bat = float(base.get("baseAttackTime") or 1.0)
    aspd = (
        float(base.get("attackSpeed") or 100)
        + pot["attack_speed"]
        + tal["attack_speed"]
        + float(module_aspd or 0)
    )
    res = float(base.get("magicResistance") or 0) + pot["res"] + tal["res"]

    return {
        "hp": hp,
        "atk": atk,
        "def": defense,
        "res": res,
        "attack_speed": aspd,
        "base_attack_time": bat,
        "talent_atk_pct": float(tal.get("atk_pct") or 0),
        "potential_atk_flat": pot["atk"],
        "potential_hp_flat": pot["hp"],
        "potential_def_flat": pot["def"],
        "potential_aspd": pot["attack_speed"],
    }


def _empty_enemy_effects() -> dict[str, float]:
    return {
        "atk_pct": 0.0,
        "atk_flat": 0.0,
        "hp_pct": 0.0,
        "hp_flat": 0.0,
        "def_pct": 0.0,
        "def_flat": 0.0,
        "res_pct": 0.0,
        "res_flat": 0.0,
    }


def _desc_targets_enemy(desc: str, attr_keys: tuple[str, ...]) -> bool:
    """描述里属性减益是否指向敌人（含「敌人/敌方/命中目标」语境）。"""
    if not desc:
        return False
    if re.search(r"(?:所有)?(?:敌人|敌方|命中目标)", desc):
        for key in attr_keys:
            # 敌方语境必须出现在属性标签之前；不能因为同一句后半段提到
            # “周围所有敌人”就把前面的自身 ATK/HP 加成判给敌人。
            if re.search(
                rf"(?:敌人|敌方|命中目标)[^。；，,\n]{{0,40}}"
                rf"\{{?-?{re.escape(key)}(?=[:}}])",
                desc,
            ):
                return True
            # 显式负号标签本身可作为敌方减益信号。
            if re.search(rf"\{{-{re.escape(key)}(?::0%)?\}}", desc):
                return True
    return False


def _attr_is_pct(desc: str, key: str) -> bool:
    """描述标签含 :0% → 百分比；否则定值。"""
    if re.search(rf"\{{-?{re.escape(key)}:0%\}}", desc):
        return True
    if re.search(rf"\{{-?{re.escape(key)}\}}", desc):
        return False
    return True  # 无标签时百分比更常见（atk/def/max_hp）


def _nested_enemy_attr(desc: str, bb: dict, attr: str) -> tuple[float, bool] | None:
    """Return an explicitly described nested enemy debuff (for example attack@def)."""
    for key, raw_value in bb.items():
        if key == attr or not re.search(rf"(?:@|\.|\]){re.escape(attr)}$", str(key)):
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            continue
        marker = re.search(rf"\{{-?{re.escape(str(key))}(?::([^}}]+))?\}}", desc)
        if not marker:
            continue
        nearby = desc[max(0, marker.start() - 90):marker.start()]
        if not re.search(r"(?:敌|目标|使其)[^。；\n]{0,70}$", nearby):
            continue
        return value, bool(marker.group(1) and "%" in marker.group(1))
    return None


def skill_multiplier_and_duration(
    skill_levels: list[dict],
    skill_level: int,
) -> dict[str, Any]:
    """从技能 blackboard 提取：面板 ATK%（atk）与命中倍率（atk_scale）分开；敌方减益进 enemy_effects。"""
    defaults = {
        "atk_scale": 1.0,
        "atk_pct": 0.0,
        "duration": 0.0,
        "name": None,
        "blackboard": [],
        "attack_speed": 0.0,
        "base_attack_time": 0.0,
        "damage_scale": 1.0,
        "secondary_scale": 0.0,
        "cnt": 1,
        "hp_pct": 0.0,
        "def_pct": 0.0,
        "res_flat": 0.0,
        "res_pct": 0.0,
        "enemy_effects": _empty_enemy_effects(),
    }
    if not skill_levels:
        return defaults

    idx = max(0, min(skill_level - 1, len(skill_levels) - 1))
    lv = skill_levels[idx]
    bb = {b.get("key"): b.get("value") for b in (lv.get("blackboard") or []) if isinstance(b, dict)}
    desc = str(lv.get("description") or "")

    # --- 命中主倍率 atk_scale（始终自身命中，不进敌人面板） ---
    scale = 1.0
    primary_key = None
    # attack@atk_scale is the recurring attack payload. A simultaneous plain
    # atk_scale usually belongs to a terminal burst or an extra damage packet,
    # so prefer the recurring payload for the single UI damage input.
    for key in ("attack@atk_scale", "atk_scale"):
        if key in bb and bb[key] is not None:
            val = float(bb[key])
            if val > 0:
                scale = val
                primary_key = key
                break

    if primary_key is None and "value" in bb and bb["value"] is not None:
        val = float(bb["value"])
        if val > 1.0:
            scale = val
            primary_key = "value"

    secondary = 0.0
    used_keys = {primary_key} if primary_key else set()
    for key, val in sorted(bb.items()):
        if key in used_keys or key == "atk":
            continue
        if key.startswith("attack@atk_scale_") or key.startswith("atk_scale_") or key == "append_atk_scale":
            try:
                v = float(val)
                if v > 0 and v > secondary:
                    secondary = v
            except (TypeError, ValueError):
                pass

    dmg_scale = 1.0
    if "damage_scale" in bb and bb["damage_scale"] is not None:
        dmg_scale = float(bb["damage_scale"])

    aspd = 0.0
    if "attack_speed" in bb and bb["attack_speed"] is not None:
        # 敌方攻速减益（初雪一技能）不进干员 aspd；描述含敌人则跳过
        if not re.search(r"(?:敌人|敌方).{0,24}攻击速度|攻击速度.{0,24}(?:敌人|敌方)", desc):
            aspd = float(bb["attack_speed"])

    bat = 0.0
    if "base_attack_time" in bb and bb["base_attack_time"] is not None:
        bat = float(bb["base_attack_time"])

    cnt = 1
    if "cnt" in bb and bb["cnt"] is not None:
        cnt = int(float(bb["cnt"]))

    atk_pct = 0.0
    hp_pct = 0.0
    def_pct = 0.0
    res_flat = 0.0
    res_pct = 0.0
    enemy_effects = _empty_enemy_effects()

    # --- ATK ---
    if "atk" in bb and bb["atk"] is not None:
        v = float(bb["atk"])
        if abs(v) > 0 and abs(v) < 5:
            if v < 0 and _desc_targets_enemy(desc, ("atk",)):
                if _attr_is_pct(desc, "atk"):
                    enemy_effects["atk_pct"] = v
                else:
                    enemy_effects["atk_flat"] = v
            else:
                atk_pct = v

    # --- HP ---
    if "max_hp" in bb and bb["max_hp"] is not None:
        v = float(bb["max_hp"])
        if abs(v) > 0:
            if v < 0 and _desc_targets_enemy(desc, ("max_hp", "hp")):
                if _attr_is_pct(desc, "max_hp") or abs(v) < 5:
                    enemy_effects["hp_pct"] = v if abs(v) < 5 else 0.0
                    if abs(v) >= 5:
                        enemy_effects["hp_flat"] = v
                else:
                    enemy_effects["hp_flat"] = v
            elif abs(v) < 5:
                hp_pct = v

    # --- DEF ---
    if "def" in bb and bb["def"] is not None:
        v = float(bb["def"])
        if abs(v) > 0:
            if v < 0 and _desc_targets_enemy(desc, ("def",)):
                if _attr_is_pct(desc, "def") or abs(v) < 5:
                    enemy_effects["def_pct"] = v if abs(v) < 5 else 0.0
                    if abs(v) >= 5:
                        enemy_effects["def_flat"] = v
                else:
                    enemy_effects["def_flat"] = v
            elif abs(v) < 5:
                def_pct = v

    # --- RES ---
    if "magic_resistance" in bb and bb["magic_resistance"] is not None:
        v = float(bb["magic_resistance"])
        to_enemy = (
            v < 0
            and _desc_targets_enemy(desc, ("magic_resistance",))
            or bool(re.search(r"\{-magic_resistance", desc))
        )
        is_pct = _attr_is_pct(desc, "magic_resistance")
        if to_enemy:
            if is_pct or abs(v) < 1:
                enemy_effects["res_pct"] = v if (is_pct or abs(v) < 5) else 0.0
                if not is_pct and abs(v) >= 1:
                    enemy_effects["res_flat"] = v
            else:
                enemy_effects["res_flat"] = v
        else:
            if is_pct:
                res_pct = v
            elif re.search(r"\{magic_resistance\}", desc) or abs(v) >= 1.0:
                res_flat = v

    # Nested keys often describe an attack payload or summon. Only parse them
    # as enemy attributes when the exact negative placeholder is in nearby
    # enemy/target context.
    for attr, pct_field, flat_field in (
        ("atk", "atk_pct", "atk_flat"),
        ("max_hp", "hp_pct", "hp_flat"),
        ("def", "def_pct", "def_flat"),
        ("magic_resistance", "res_pct", "res_flat"),
    ):
        nested = _nested_enemy_attr(desc, bb, attr)
        if nested is None:
            continue
        value, is_pct = nested
        field = pct_field if is_pct else flat_field
        if enemy_effects[field] == 0:
            enemy_effects[field] = value

    duration = float(lv.get("duration") or 0)
    if duration < 0:
        duration = 0

    return {
        "atk_scale": scale,
        "atk_pct": atk_pct,
        "duration": duration,
        "name": lv.get("name"),
        "blackboard": lv.get("blackboard") or [],
        "description": lv.get("description"),
        "attack_speed": aspd,
        "base_attack_time": bat,
        "damage_scale": dmg_scale,
        "secondary_scale": secondary,
        "cnt": cnt,
        "hp_pct": hp_pct,
        "def_pct": def_pct,
        "res_flat": res_flat,
        "res_pct": res_pct,
        "enemy_effects": enemy_effects,
    }
