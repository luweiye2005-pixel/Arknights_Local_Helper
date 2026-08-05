"""伤害结算：实装口径物理减法保底 + 最终乘算/受伤加深。"""
from __future__ import annotations

from typing import Any, Literal


DamageType = Literal["PHYS", "MAGIC", "TRUE", "ELEMENTAL"]


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
    elemental_damage_taken_pct: float = 0.0,
) -> dict[str, float]:
    """
    单次伤害结算。
    scale：最终乘算积（提升至×造成%）。
    damage_pct：遗物等通用伤害加深（与类型加深分开）。
    真伤不吃物理免伤。
    """
    hit_atk = atk * scale
    if damage_type == "ELEMENTAL":
        basic = hit_atk
        taken = 1.0 + damage_pct + elemental_damage_taken_pct
        reduction = 1.0
    elif damage_type == "TRUE":
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

    dtype: DamageType = "TRUE" if true_damage else (
        damage_type if damage_type in ("PHYS", "MAGIC", "TRUE", "ELEMENTAL") else "PHYS"
    )

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
        elemental_damage_taken_pct=float(enemy_manual.get("elemental_damage_taken_pct") or 0),
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
    elif dtype == "TRUE":
        steps.append(f"真伤：结算ATK={detail['basic']:.2f}（不吃物理免伤）")
        steps.append(f"乘区：×受伤加深{detail['taken_mul']:.4f} → 单次伤害={detail['final']:.2f}")
    else:
        steps.append(f"元素伤害：结算值={detail['basic']:.2f}（不经过防御与法抗）")
        steps.append(f"元素受伤加深×{detail['taken_mul']:.4f} → 单次元素伤害={detail['final']:.2f}")

    return {
        "damage_type": dtype,
        "final_mul": final_mul,
        "hit_atk": detail["hit_atk"],
        "basic_damage": detail["basic"],
        "hit_damage": detail["final"],
        "steps": steps,
    }
