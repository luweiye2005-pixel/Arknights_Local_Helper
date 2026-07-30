"""面板计算：基础面板 + 藏品加成 + 技能手填 + 单次伤害过程。"""
from __future__ import annotations

from typing import Any

from app.combat.attributes import calc_operator_panel
from app.combat.engine import attack_interval, resolve_hit_from_panels
from app.combat.relics import (
    build_conditional_relic_modifiers,
    build_enemy_relic_modifiers,
    build_relic_modifiers,
    get_outer_buff,
    manual_bonus_to_modifiers,
    outer_buff_to_modifiers,
)
from app.data import db as gdb


def calculate_panel(payload: dict[str, Any]) -> dict[str, Any]:
    op_id = payload.get("operator_id") or None
    enemy_id = payload.get("enemy_id") or None
    if not op_id and not enemy_id:
        raise ValueError("请选择干员或敌人")

    elite = int(payload.get("elite") or 0)
    level = int(payload.get("level") or 1)
    favor = int(payload.get("favor_percent") or 100)
    potential = int(payload.get("potential") or 0)
    module_id = payload.get("module_id")
    module_level = int(payload.get("module_level") or 1)
    theme_id = payload.get("theme_id")
    equivalent_grade = int(payload.get("equivalent_grade") or 0)
    enemy_level_index = int(payload.get("enemy_level") or 0)
    apply_outer_buff = bool(payload.get("apply_outer_buff", True))
    manual_bonus = payload.get("manual_bonus") or {}
    relic_conditions = payload.get("relic_conditions") or {}
    skill_manual = payload.get("skill_manual") or {}
    enemy_manual = payload.get("enemy_manual") or {}
    damage_type = payload.get("damage_type") or "PHYS"
    if damage_type not in ("PHYS", "MAGIC", "TRUE"):
        damage_type = "PHYS"

    skill_atk_pct = float(skill_manual.get("atk_pct") or 0)

    relic_ids = list(payload.get("relic_ids") or [])
    relics_applied = []
    for rid in relic_ids:
        resolved = gdb.resolve_relic_for_grade(rid, equivalent_grade) or gdb.get_relic_row(rid)
        if resolved:
            relics_applied.append(
                {
                    "id": resolved.get("id") or rid,
                    "base_id": rid,
                    "name": resolved.get("name"),
                }
            )

    result: dict[str, Any] = {
        "model": "arknights_phys_sub_v1",
        "operator": None,
        "enemy": None,
        "config": {
            "elite": elite,
            "level": level,
            "favor_percent": favor,
            "potential": potential,
            "module_id": module_id,
            "module_level": module_level,
            "theme_id": theme_id,
            "equivalent_grade": equivalent_grade,
            "enemy_id": enemy_id,
            "enemy_level": enemy_level_index,
            "apply_outer_buff": apply_outer_buff,
            "manual_bonus": manual_bonus,
            "relic_conditions": relic_conditions,
            "skill_manual": skill_manual,
            "enemy_manual": enemy_manual,
            "damage_type": damage_type,
        },
        "module": None,
        "base_panel": None,
        "bonus": {
            "theme_id": theme_id,
            "equivalent_grade": equivalent_grade,
        },
        "modifiers": None,
        "final_panel": None,
        "enemy_final_panel": None,
        "hit_damage": None,
        "hit_detail": None,
        "relics_applied": relics_applied,
        "outer_buff": None,
        "steps": [],
    }
    steps: list[str] = []
    combat_atk = 0.0
    total_mods = None
    enemy_final = None

    if op_id:
        operator = gdb.get_operator_detail(op_id)
        if not operator:
            raise ValueError(f"未找到干员: {op_id}")

        module_atk_flat = float(payload.get("module_atk_flat") or 0)
        module_atk_pct = float(payload.get("module_atk_pct") or 0)
        module_meta = None
        module_aspd = 0.0

        if module_id:
            chosen = next((m for m in (operator.get("modules") or []) if m.get("id") == module_id), None)
            if chosen:
                levels = chosen.get("levels") or []
                lv = next((x for x in levels if int(x.get("level") or 0) == module_level), None)
                if lv is None and levels:
                    idx = max(0, min(module_level - 1, len(levels) - 1))
                    lv = levels[idx]
                if lv:
                    module_atk_flat += float(lv.get("atk") or 0)
                    module_atk_pct += float(lv.get("atk_pct") or 0)
                    module_aspd += float(lv.get("attack_speed") or 0)
                    module_meta = {
                        "id": module_id,
                        "name": chosen.get("name"),
                        "type": chosen.get("type"),
                        "level": module_level,
                        "atk": lv.get("atk"),
                        "atk_pct": lv.get("atk_pct"),
                        "hp": lv.get("hp"),
                        "defense": lv.get("defense"),
                        "attack_speed": lv.get("attack_speed"),
                    }

        base = calc_operator_panel(
            operator,
            elite=elite,
            level=level,
            favor_percent=favor,
            potential=potential,
            module_atk_flat=module_atk_flat,
            module_atk_pct=module_atk_pct,
        )
        base["attack_speed"] = float(base.get("attack_speed") or 100) + module_aspd
        base_interval = attack_interval(base["base_attack_time"], base["attack_speed"])

        relic_mods = build_relic_modifiers(relic_ids=relic_ids, equivalent_grade=equivalent_grade)
        cond_mods = build_conditional_relic_modifiers(
            relic_ids, relic_conditions, operator=operator
        )
        mods = relic_mods.merge(cond_mods)

        outer_raw = get_outer_buff(theme_id) if apply_outer_buff else None
        outer_mods = outer_buff_to_modifiers(outer_raw if apply_outer_buff else None)
        manual_mods = manual_bonus_to_modifiers(manual_bonus if isinstance(manual_bonus, dict) else {})

        total = mods.merge(outer_mods).merge(manual_mods)
        total_mods = total

        # 直接乘算：藏品/条件/局外/手填ATK% + 技能「攻击力+%」加算
        direct_atk_pct = total.atk_pct + skill_atk_pct
        combat_atk = base["atk"] * (1.0 + direct_atk_pct) + total.atk_flat
        final_hp = base["hp"] * (1.0 + total.hp_pct)
        final_def = base["def"] * (1.0 + total.def_pct)
        final_aspd = base["attack_speed"] + total.aspd
        final_interval = attack_interval(base["base_attack_time"], final_aspd)

        relic_dmg = total.damage_pct
        if damage_type == "PHYS":
            relic_dmg += total.phys_damage_pct
        elif damage_type == "MAGIC":
            relic_dmg += total.arts_damage_pct

        final = {
            "hp": final_hp,
            "atk": combat_atk,
            "def": final_def,
            "res": base["res"],
            "attack_speed": final_aspd,
            "base_attack_time": base["base_attack_time"],
            "attack_interval": final_interval,
            "damage_pct": relic_dmg,
            "ignore_def_pct": total.ignore_def_pct,
            "true_damage": total.true_damage,
            "skill_atk_pct": skill_atk_pct,
            "direct_atk_pct": direct_atk_pct,
        }

        result["operator"] = {
            "id": op_id,
            "name": operator.get("name"),
            "profession_cn": operator.get("profession_cn"),
            "position": operator.get("position"),
            "position_cn": operator.get("position_cn"),
        }
        result["module"] = module_meta
        result["base_panel"] = {**base, "attack_interval": base_interval}
        result["final_panel"] = final
        result["modifiers"] = total.to_dict()
        result["outer_buff"] = outer_raw
        result["bonus"].update(
            {
                "atk_flat_from_module": module_atk_flat,
                "atk_pct_from_module": module_atk_pct,
                "atk_pct_from_relics": relic_mods.atk_pct,
                "atk_flat_from_relics": relic_mods.atk_flat,
                "hp_pct_from_relics": relic_mods.hp_pct,
                "def_pct_from_relics": relic_mods.def_pct,
                "aspd_from_relics": relic_mods.aspd,
                "atk_pct_from_conditions": cond_mods.atk_pct,
                "aspd_from_conditions": cond_mods.aspd,
                "atk_pct_from_outer": outer_mods.atk_pct,
                "hp_pct_from_outer": outer_mods.hp_pct,
                "def_pct_from_outer": outer_mods.def_pct,
                "aspd_from_outer": outer_mods.aspd,
                "atk_pct_from_manual": manual_mods.atk_pct,
                "hp_pct_from_manual": manual_mods.hp_pct,
                "def_pct_from_manual": manual_mods.def_pct,
                "aspd_from_manual": manual_mods.aspd,
                "atk_pct_from_skill": skill_atk_pct,
                "apply_outer_buff": apply_outer_buff,
                "damage_pct": final["damage_pct"],
                "ignore_def_pct": total.ignore_def_pct,
                "true_damage": total.true_damage,
            }
        )

        steps.append("—— 面板计算 ——")
        if module_meta:
            steps.append(
                f"1. 模组「{module_meta.get('name')}」{module_meta.get('type')} Lv{module_meta.get('level')}："
                f"ATK+{module_meta.get('atk')} ATK%+{float(module_meta.get('atk_pct') or 0):.0%} "
                f"攻速+{module_meta.get('attack_speed')}"
            )
        steps.append(
            f"2. 养成+模组基础 ATK={base['atk']:.2f} HP={base['hp']:.0f} DEF={base['def']:.0f} "
            f"攻速={base['attack_speed']:.1f} 间隔={base_interval:.3f}s"
        )
        steps.append(
            f"3. 直接乘算分项：藏品ATK%={relic_mods.atk_pct:.2%} + 条件ATK%={cond_mods.atk_pct:.2%} "
            f"+ 局外ATK%={outer_mods.atk_pct:.2%} + 手填ATK%={manual_mods.atk_pct:.2%} "
            f"+ 技能ATK%={skill_atk_pct:.2%} = {direct_atk_pct:.2%}；"
            f"固定ATK+={total.atk_flat:.1f}"
        )
        steps.append(
            f"4. 战斗面板 ATK = {base['atk']:.2f} × (1+{direct_atk_pct:.4f}) + {total.atk_flat:.1f} "
            f"= {combat_atk:.2f}；HP={final_hp:.0f} DEF={final_def:.0f} 攻速={final_aspd:.1f}"
        )

    if enemy_id:
        enemy = gdb.get_enemy_row(
            enemy_id,
            level=enemy_level_index,
            theme_id=theme_id,
            equivalent_grade=equivalent_grade,
        )
        if not enemy:
            raise ValueError(f"未找到敌人: {enemy_id}")

        attrs = dict(enemy.get("attributes") or {})
        emods = build_enemy_relic_modifiers(relic_ids=relic_ids, equivalent_grade=equivalent_grade)
        enemy_final = {
            "hp": float(attrs.get("hp") or 0) * (1.0 + emods.hp_pct),
            "atk": float(attrs.get("atk") or 0) * (1.0 + emods.atk_pct),
            "def": float(attrs.get("def") or 0) * (1.0 + emods.def_pct),
            "magic_resistance": float(attrs.get("magic_resistance") or 0) + emods.res_flat,
            "attack_speed": float(attrs.get("attack_speed") or 0) + emods.aspd,
            "move_speed": float(attrs.get("move_speed") or 0),
            "range_radius": float(attrs.get("range_radius") or 0),
            "damage_type": attrs.get("damage_type"),
        }
        result["enemy"] = {
            "id": enemy.get("id"),
            "name": enemy.get("name"),
            "enemy_level": enemy.get("enemy_level"),
            "level_index": enemy.get("level_index"),
        }
        result["enemy_final_panel"] = enemy_final
        result["bonus"]["enemy_hp_pct_from_relics"] = emods.hp_pct
        result["bonus"]["enemy_atk_pct_from_relics"] = emods.atk_pct
        result["bonus"]["enemy_def_pct_from_relics"] = emods.def_pct
        result["bonus"]["enemy_aspd_from_relics"] = emods.aspd
        result["bonus"]["enemy_res_flat_from_relics"] = emods.res_flat
        result["bonus"]["enemy_difficulty_mods"] = enemy.get("difficulty_mods") or []

        steps.append("—— 敌人面板 ——")
        steps.append(
            f"敌人「{enemy.get('name')}」最终 "
            f"HP={enemy_final['hp']:.0f} DEF={enemy_final['def']:.0f} "
            f"RES={enemy_final['magic_resistance']:.1f}"
        )

    # 干员+敌人 → 单次伤害
    if op_id and enemy_final is not None and combat_atk > 0:
        relic_dmg = 0.0
        ignore = 0.0
        true_dmg = False
        if total_mods is not None:
            relic_dmg = float(total_mods.damage_pct or 0)
            if damage_type == "PHYS":
                relic_dmg += float(total_mods.phys_damage_pct or 0)
            elif damage_type == "MAGIC":
                relic_dmg += float(total_mods.arts_damage_pct or 0)
            ignore = float(total_mods.ignore_def_pct or 0)
            true_dmg = bool(total_mods.true_damage)

        hit_info = resolve_hit_from_panels(
            combat_atk,
            damage_type=damage_type,  # type: ignore[arg-type]
            enemy_def=float(enemy_final["def"]),
            enemy_res=float(enemy_final["magic_resistance"]),
            skill_manual=skill_manual,
            enemy_manual=enemy_manual if isinstance(enemy_manual, dict) else {},
            relic_damage_pct=relic_dmg,
            ignore_def_pct=ignore,
            true_damage=true_dmg,
        )
        result["hit_damage"] = hit_info["hit_damage"]
        result["hit_detail"] = hit_info
        steps.append("—— 单次伤害 ——")
        steps.extend(hit_info["steps"])

    result["steps"] = steps
    return result
