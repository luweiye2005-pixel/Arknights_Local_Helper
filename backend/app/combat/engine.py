"""伤害结算：实装口径物理减法保底 + 最终乘算/受伤加深。"""
from __future__ import annotations

import math
from typing import Any, Literal

from app.combat.attributes import calc_operator_panel, skill_multiplier_and_duration
from app.combat.relics import CombatModifiers, build_relic_modifiers
from app.data.store import get_store

DamageType = Literal["PHYS", "MAGIC", "TRUE"]


def physical_damage(
    atk: float,
    defense: float,
    ignore_def_pct: float = 0.0,
    flat_def_reduce: float = 0.0,
    def_pct_reduce: float = 0.0,
) -> float:
    """物伤：max(5%×ATK, ATK − 有效防御)。"""
    if atk <= 0:
        return 0.0
    # 先固定减防，再百分比减防，再百分比无视
    def_after_flat = max(0.0, defense - flat_def_reduce)
    def_after_pct = def_after_flat * max(0.0, 1.0 - def_pct_reduce)
    effective_def = max(0.0, def_after_pct * (1.0 - ignore_def_pct))
    return max(atk * 0.05, atk - effective_def)


def arts_damage(atk: float, res: float, ignore_res: float = 0.0) -> float:
    """法伤：RES 是固定值减法而非百分比（如无视20法抗 → RES−20）。"""
    res = max(0.0, min(100.0, res - ignore_res))
    return max(atk * 0.05, atk * (1.0 - res / 100.0))


def attack_interval(base_attack_time: float, attack_speed: float) -> float:
    aspd = max(1.0, attack_speed)
    return base_attack_time * 100.0 / aspd


def product_atk_scales(atk_scale_to_pcts: list[float] | None, damage_scale_pct: float = 100.0) -> float:
    """提升至% 列表相乘 × 造成攻击力%。填 125 表示 1.25；造成伤害默认 100→×1。"""
    mul = 1.0
    for pct in atk_scale_to_pcts or []:
        try:
            v = float(pct)
        except (TypeError, ValueError):
            continue
        if v <= 0:
            continue
        mul *= v / 100.0
    try:
        dmg_scale = float(damage_scale_pct)
    except (TypeError, ValueError):
        dmg_scale = 100.0
    if dmg_scale <= 0:
        dmg_scale = 100.0
    return mul * (dmg_scale / 100.0)


def calc_hit_damage(
    atk: float,
    damage_type: DamageType,
    enemy_def: float,
    enemy_res: float,
    scale: float = 1.0,
    damage_pct: float = 0.0,
    ignore_def_pct: float = 0.0,
    ignore_res: float = 0.0,
    flat_def_reduce: float = 0.0,
    def_pct_reduce: float = 0.0,
    phys_damage_taken_pct: float = 0.0,
    phys_damage_reduction: float = 0.0,
    arts_damage_taken_pct: float = 0.0,
    arts_damage_reduction: float = 0.0,
    true_damage_taken_pct: float = 0.0,
) -> dict[str, float]:
    """
    单次伤害结算。
    scale：最终乘算积（提升至×造成%）。
    damage_pct：遗物等通用伤害加深（与类型加深分开）。
    真伤不吃物理免伤。
    """
    hit_atk = atk * scale
    if damage_type == "TRUE":
        basic = hit_atk
        taken = 1.0 + damage_pct + true_damage_taken_pct
        reduction = 1.0
    elif damage_type == "MAGIC":
        basic = arts_damage(hit_atk, enemy_res, ignore_res=ignore_res)
        taken = 1.0 + damage_pct + arts_damage_taken_pct
        reduction = max(0.0, 1.0 - arts_damage_reduction)
    else:
        basic = physical_damage(
            hit_atk,
            enemy_def,
            ignore_def_pct=ignore_def_pct,
            flat_def_reduce=flat_def_reduce,
            def_pct_reduce=def_pct_reduce,
        )
        taken = 1.0 + damage_pct + phys_damage_taken_pct
        reduction = max(0.0, 1.0 - phys_damage_reduction)

    final = basic * taken * reduction
    return {
        "hit_atk": hit_atk,
        "basic": basic,
        "taken_mul": taken,
        "reduction_mul": reduction,
        "final": final,
    }


def resolve_hit_from_panels(
    combat_atk: float,
    *,
    damage_type: DamageType = "PHYS",
    enemy_def: float = 0.0,
    enemy_res: float = 0.0,
    skill_manual: dict[str, Any] | None = None,
    enemy_manual: dict[str, Any] | None = None,
    relic_damage_pct: float = 0.0,
    ignore_def_pct: float = 0.0,
    true_damage: bool = False,
) -> dict[str, Any]:
    """由战斗面板 ATK + 手填技能/敌人修正得到单次伤害与过程。"""
    skill_manual = skill_manual or {}
    enemy_manual = enemy_manual or {}

    scale_to = skill_manual.get("atk_scale_to") or []
    if not isinstance(scale_to, list):
        scale_to = [scale_to] if scale_to else []
    damage_scale_pct = float(skill_manual.get("damage_scale_pct") if skill_manual.get("damage_scale_pct") is not None else 100)
    final_mul = product_atk_scales([float(x) for x in scale_to if x is not None and float(x) > 0], damage_scale_pct)

    dtype: DamageType = "TRUE" if true_damage else (damage_type if damage_type in ("PHYS", "MAGIC", "TRUE") else "PHYS")

    ignore_def = float(enemy_manual.get("ignore_def_pct") or 0) + float(ignore_def_pct or 0)
    ignore_def = min(1.0, max(0.0, ignore_def))
    ignore_res_val = max(0.0, float(enemy_manual.get("ignore_res") or 0))

    detail = calc_hit_damage(
        atk=combat_atk,
        damage_type=dtype,
        enemy_def=float(enemy_def or 0),
        enemy_res=float(enemy_res or 0),
        scale=final_mul,
        damage_pct=float(relic_damage_pct or 0),
        ignore_def_pct=ignore_def,
        ignore_res=ignore_res_val,
        flat_def_reduce=float(enemy_manual.get("flat_def_reduce") or 0),
        def_pct_reduce=float(enemy_manual.get("def_pct_reduce") or 0),
        phys_damage_taken_pct=float(enemy_manual.get("phys_damage_taken_pct") or 0),
        phys_damage_reduction=float(enemy_manual.get("phys_damage_reduction") or 0),
        arts_damage_taken_pct=float(enemy_manual.get("arts_damage_taken_pct") or 0),
        arts_damage_reduction=float(enemy_manual.get("arts_damage_reduction") or 0),
        true_damage_taken_pct=float(enemy_manual.get("true_damage_taken_pct") or 0),
    )

    scale_bits = []
    for pct in scale_to:
        try:
            v = float(pct)
        except (TypeError, ValueError):
            continue
        if v > 0:
            scale_bits.append(f"{v:g}%")
    scale_desc = " × ".join(scale_bits) if scale_bits else "100%"
    steps = [
        f"最终乘算：提升至({scale_desc}) × 造成伤害{damage_scale_pct:g}% → 倍率={final_mul:.4f}",
        f"结算 ATK = 战斗面板ATK {combat_atk:.2f} × {final_mul:.4f} = {detail['hit_atk']:.2f}",
    ]
    if dtype == "PHYS":
        steps.append(
            f"物理：max(5%×结算ATK, 结算ATK−有效防御) = {detail['basic']:.2f}"
            f"（敌DEF={float(enemy_def or 0):.1f}，无视防={ignore_def:.2%}）"
        )
        steps.append(
            f"乘区：×受伤加深{detail['taken_mul']:.4f} ×(1−物免){detail['reduction_mul']:.4f}"
            f" → 单次伤害={detail['final']:.2f}"
        )
    elif dtype == "MAGIC":
        steps.append(
            f"法术：max(5%×结算ATK, 结算ATK×(1−有效RES/100)) = {detail['basic']:.2f}"
            f"（敌RES={float(enemy_res or 0):.1f}，无视法抗={ignore_res_val:.0f} → 有效RES={max(0.0, float(enemy_res or 0) - ignore_res_val):.1f}）"
        )
        steps.append(
            f"乘区：×受伤加深{detail['taken_mul']:.4f} ×(1−法免){detail['reduction_mul']:.4f}"
            f" → 单次伤害={detail['final']:.2f}"
        )
    else:
        steps.append(f"真伤：结算ATK={detail['basic']:.2f}（不吃物理免伤）")
        steps.append(f"乘区：×受伤加深{detail['taken_mul']:.4f} → 单次伤害={detail['final']:.2f}")

    return {
        "damage_type": dtype,
        "final_mul": final_mul,
        "hit_atk": detail["hit_atk"],
        "basic_damage": detail["basic"],
        "hit_damage": detail["final"],
        "steps": steps,
    }


def calculate_damage(payload: dict[str, Any]) -> dict[str, Any]:
    """兼容旧入口：干员 + 敌人 → 单次伤害/TTK（走同一套 hit 公式）。"""
    store = get_store()
    op_id = payload["operator_id"]
    enemy_id = payload["enemy_id"]
    operator = store.get_operator(op_id)
    if not operator:
        raise ValueError(f"未找到干员: {op_id}")

    enemy_level = int(payload.get("enemy_level") or 0)
    enemy = store.get_enemy(enemy_id, level=enemy_level)
    if not enemy:
        raise ValueError(f"未找到敌人: {enemy_id}")

    elite = int(payload.get("elite") or 0)
    level = int(payload.get("level") or 1)
    favor = int(payload.get("favor_percent") or 100)
    potential = int(payload.get("potential") or 0)
    skill_index = int(payload.get("skill_index") or 0)
    skill_level = int(payload.get("skill_level") or 7)
    damage_type: DamageType = payload.get("damage_type") or "PHYS"
    if damage_type not in ("PHYS", "MAGIC", "TRUE"):
        damage_type = "PHYS"

    module_atk_flat = float(payload.get("module_atk_flat") or 0)
    module_atk_pct = float(payload.get("module_atk_pct") or 0)

    module_id = payload.get("module_id")
    module_level = int(payload.get("module_level") or 1)
    module_meta = None
    if module_id:
        mods_list = operator.get("modules") or []
        chosen = next((m for m in mods_list if m.get("id") == module_id), None)
        if chosen:
            levels = chosen.get("levels") or []
            lv = None
            for item in levels:
                if int(item.get("level") or 0) == module_level:
                    lv = item
                    break
            if lv is None and levels:
                idx = max(0, min(module_level - 1, len(levels) - 1))
                lv = levels[idx]
            if lv:
                module_atk_flat += float(lv.get("atk") or 0)
                module_atk_pct += float(lv.get("atk_pct") or 0)
                module_meta = {
                    "id": module_id,
                    "name": chosen.get("name"),
                    "type": chosen.get("type"),
                    "level": module_level,
                    "atk": lv.get("atk"),
                    "atk_pct": lv.get("atk_pct"),
                }

    relic_ids = payload.get("relic_ids") or []
    relics = []
    for rid in relic_ids:
        r = store.get_relic(rid)
        if r:
            relics.append(r)

    mods: CombatModifiers = build_relic_modifiers(relics)
    skill_manual = payload.get("skill_manual") or {}
    skill_atk_pct = float(skill_manual.get("atk_pct") or 0)

    panel = calc_operator_panel(
        operator,
        elite=elite,
        level=level,
        favor_percent=favor,
        potential=potential,
        module_atk_flat=module_atk_flat + mods.atk_flat,
        module_atk_pct=module_atk_pct,
    )
    combat_atk = panel["atk"] * (1.0 + mods.atk_pct + skill_atk_pct)
    aspd = panel["attack_speed"] + mods.aspd
    interval = attack_interval(panel["base_attack_time"], aspd)

    # 若未选手填倍率，回退到技能表：atk→面板%，atk_scale→造成%
    if not skill_manual.get("atk_scale_to") and skill_manual.get("damage_scale_pct") in (None, 100) and not skill_atk_pct:
        skills = operator.get("skills") or []
        skill_info = {"atk_scale": 1.0, "atk_pct": 0.0, "duration": 0.0, "name": "普攻"}
        if skills and 0 <= skill_index < len(skills):
            skill_info = skill_multiplier_and_duration(skills[skill_index].get("levels") or [], skill_level)
        scale = float(skill_info.get("atk_scale") or 1.0)
        skill_atk_pct = float(skill_info.get("atk_pct") or 0)
        combat_atk = panel["atk"] * (1.0 + mods.atk_pct + skill_atk_pct)
        skill_manual = {
            **skill_manual,
            "atk_pct": skill_atk_pct,
            "atk_scale_to": [],
            "damage_scale_pct": scale * 100.0,
        }
        duration = float(skill_info.get("duration") or 0.0)
        skill_name = skill_info.get("name")
    else:
        duration = float(payload.get("skill_duration") or 0)
        skill_name = "手填技能"

    eattr = enemy.get("attributes") or {}
    enemy_hp = float(payload.get("enemy_hp") if payload.get("enemy_hp") is not None else (eattr.get("hp") or 0))
    enemy_def = float(payload.get("enemy_def") if payload.get("enemy_def") is not None else (eattr.get("def") or 0))
    enemy_res = float(
        payload.get("enemy_res") if payload.get("enemy_res") is not None else (eattr.get("magic_resistance") or 0)
    )

    dmg_pct = mods.damage_pct
    if damage_type == "PHYS":
        dmg_pct += mods.phys_damage_pct
    elif damage_type == "MAGIC":
        dmg_pct += mods.arts_damage_pct

    hit_info = resolve_hit_from_panels(
        combat_atk,
        damage_type=damage_type,
        enemy_def=enemy_def,
        enemy_res=enemy_res,
        skill_manual=skill_manual,
        enemy_manual=payload.get("enemy_manual") or {},
        relic_damage_pct=dmg_pct,
        ignore_def_pct=mods.ignore_def_pct,
        true_damage=mods.true_damage,
    )
    hit = hit_info["hit_damage"]

    if hit <= 0:
        hits = None
        ttk = None
    else:
        hits = int(math.ceil(enemy_hp / hit)) if enemy_hp > 0 else None
        ttk = (hits - 1) * interval if hits else None

    hits_in_skill = int(math.floor(duration / interval)) + 1 if duration > 0 and interval > 0 else 0
    skill_total = hits_in_skill * hit if hits_in_skill else 0
    dps = hit / interval if interval > 0 else 0

    steps = [
        f"养成+模组面板 ATK={panel['atk']:.2f}",
        f"直接乘算：藏品ATK%={mods.atk_pct:.2%} + 技能ATK%={skill_atk_pct:.2%} → 战斗面板ATK={combat_atk:.2f}",
        *hit_info["steps"],
        f"攻速={aspd:.1f}，间隔={interval:.3f}s，DPS≈{dps:.1f}",
    ]
    if hits and ttk is not None:
        steps.append(f"击杀次数={hits}，TTK≈{ttk:.2f}s")

    return {
        "model": "arknights_phys_sub_v1",
        "operator": {"id": op_id, "name": operator.get("name")},
        "enemy": {"id": enemy_id, "name": enemy.get("name"), "level_index": enemy_level},
        "panel": panel,
        "module": module_meta,
        "effective_atk": combat_atk,
        "attack_interval": interval,
        "skill": {"name": skill_name, "atk_scale": hit_info["final_mul"], "duration": duration},
        "modifiers": mods.to_dict(),
        "hit_damage": hit,
        "dps": dps,
        "enemy_hp": enemy_hp,
        "hits_to_kill": hits,
        "time_to_kill_sec": ttk,
        "hits_in_skill": hits_in_skill,
        "skill_total_damage": skill_total,
        "can_kill_in_skill": bool(enemy_hp > 0 and skill_total >= enemy_hp),
        "steps": steps,
        "relics_applied": [{"id": r["id"], "name": r.get("name")} for r in relics],
    }
