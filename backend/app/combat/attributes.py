"""面板属性计算（简化版）。"""
from __future__ import annotations

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
    """信赖加成（0-100 → 0-200 favor 内部值近似用 percent）。"""
    if not favor_frames:
        return {}
    # favorKeyFrames 通常 level 0 与 50（对应 100% 信赖）
    frames = sorted(favor_frames, key=lambda f: f.get("level", 0))
    # 用 0-100 映射到最后一帧
    t = max(0.0, min(1.0, favor_percent / 100.0))
    lo = frames[0].get("data") or {}
    hi = frames[-1].get("data") or {}
    out = {}
    for k in set(lo) | set(hi):
        a = float(lo.get(k) or 0)
        b = float(hi.get(k) or 0)
        out[k] = a + (b - a) * t
    return out


def calc_operator_panel(
    operator: dict[str, Any],
    elite: int,
    level: int,
    favor_percent: int = 100,
    potential: int = 0,
    module_atk_flat: float = 0,
    module_atk_pct: float = 0,
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

    atk = float(base.get("atk") or 0) + float(fav.get("atk") or 0)
    # 潜能：简化为每级 +2% ATK（占位，真实潜能差异很大）
    atk *= 1 + 0.02 * max(0, min(potential, 5))
    atk = atk * (1 + module_atk_pct) + module_atk_flat

    bat = float(base.get("baseAttackTime") or 1.0)
    aspd = float(base.get("attackSpeed") or 100)

    return {
        "hp": float(base.get("maxHp") or 0) + float(fav.get("maxHp") or 0),
        "atk": atk,
        "def": float(base.get("def") or 0) + float(fav.get("def") or 0),
        "res": float(base.get("magicResistance") or 0),
        "attack_speed": aspd,
        "base_attack_time": bat,
    }


def skill_multiplier_and_duration(
    skill_levels: list[dict],
    skill_level: int,
) -> dict[str, Any]:
    """从技能 blackboard 提取攻击倍率、攻速、间隔与持续时间。"""
    defaults = {
        "atk_scale": 1.0, "duration": 0.0, "name": None,
        "blackboard": [], "attack_speed": 0.0, "base_attack_time": 0.0,
        "damage_scale": 1.0, "secondary_scale": 0.0, "cnt": 1,
        "hp_pct": 0.0, "def_pct": 0.0,
    }
    if not skill_levels:
        return defaults

    idx = max(0, min(skill_level - 1, len(skill_levels) - 1))
    lv = skill_levels[idx]
    bb = {b.get("key"): b.get("value") for b in (lv.get("blackboard") or []) if isinstance(b, dict)}

    # --- 收集所有候选倍率 key，取最大值作为主倍率 ---
    def _to_scale(k: str, v: float) -> float:
        """将 blackboard 值转换为 ATK 倍率。"""
        if v <= 0:
            return 0.0
        if k == "atk":
            # atk 一律是加算百分比（0.4→+40%, 1.5→+150%, 2.3→+230%）
            if v < 5:
                return 1.0 + v
        return v  # atk_scale / attack@atk_scale / damage_scale / value

    candidates: list[tuple[str, float]] = []
    for key in ("atk_scale", "attack@atk_scale", "damage_scale", "value", "atk"):
        if key in bb and bb[key] is not None:
            val = float(bb[key])
            s = _to_scale(key, val)
            if s > 1.0:
                candidates.append((key, s))

    # 主倍率 = 值最大的候选
    scale = 1.0
    primary_key = None
    if candidates:
        candidates.sort(key=lambda x: -x[1])
        primary_key, scale = candidates[0]

    # --- 次要倍率: 其余候选 + attack@atk_scale_* / append_atk_scale ---
    secondary = 0.0
    used_keys = {primary_key} if primary_key else set()
    # 先看其他候选
    for key, s in candidates[1:]:
        if s > secondary:
            secondary = s
        used_keys.add(key)
    # 再看命名空间 key
    for key, val in sorted(bb.items()):
        if key in used_keys:
            continue
        if key.startswith("attack@atk_scale_") or key.startswith("atk_scale_") or key == "append_atk_scale":
            try:
                v = float(val)
                if v > 0 and v > secondary:
                    secondary = v
            except (TypeError, ValueError):
                pass

    # --- damage_scale（独立字段） ---
    dmg_scale = 1.0
    if "damage_scale" in bb and bb["damage_scale"] is not None:
        dmg_scale = float(bb["damage_scale"])

    # --- 攻速 ---
    aspd = 0.0
    if "attack_speed" in bb and bb["attack_speed"] is not None:
        aspd = float(bb["attack_speed"])

    # --- 攻击间隔 ---
    bat = 0.0
    if "base_attack_time" in bb and bb["base_attack_time"] is not None:
        bat = float(bb["base_attack_time"])

    # --- 攻击次数 ---
    cnt = 1
    if "cnt" in bb and bb["cnt"] is not None:
        cnt = int(float(bb["cnt"]))

    # --- HP 变化（加算百分比，同 atk） ---
    hp_pct = 0.0
    if "max_hp" in bb and bb["max_hp"] is not None:
        v = float(bb["max_hp"])
        if 0 < v < 5:
            hp_pct = v

    # --- DEF 变化（加算百分比） ---
    def_pct = 0.0
    if "def" in bb and bb["def"] is not None:
        v = float(bb["def"])
        if 0 < v < 5:
            def_pct = v

    duration = float(lv.get("duration") or 0)
    if duration < 0:
        duration = 0

    return {
        "atk_scale": scale,
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
    }
