"""面板计算：基础面板 + 藏品加成 + 技能手填 + 单次伤害过程。"""
from __future__ import annotations

from typing import Any

from app.combat.attributes import calc_operator_panel
from app.combat.engine import attack_interval, resolve_hit_from_panels
from app.combat.relics import (
    build_conditional_relic_modifiers,
    build_enemy_relic_modifiers,
    build_relic_contributions,
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
    skill_hp_pct = float(skill_manual.get("hp_pct") or 0)
    skill_def_pct = float(skill_manual.get("def_pct") or 0)
    skill_aspd = float(skill_manual.get("aspd") or 0)
    skill_res_flat = float(skill_manual.get("res_flat") or 0)
    skill_res_pct = float(skill_manual.get("res_pct") or 0)

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
        "relic_contributions": None,
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
        module_hp_flat = 0.0
        module_def_flat = 0.0
        module_aspd = 0.0
        module_meta = None

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
                    module_hp_flat += float(lv.get("hp") or 0)
                    module_def_flat += float(lv.get("defense") or 0)
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
            module_hp_flat=module_hp_flat,
            module_def_flat=module_def_flat,
            module_aspd=module_aspd,
            apply_talents=True,
        )
        base_interval = attack_interval(base["base_attack_time"], base["attack_speed"])

        relic_mods = build_relic_modifiers(relic_ids=relic_ids, equivalent_grade=equivalent_grade)
        cond_mods = build_conditional_relic_modifiers(
            relic_ids, relic_conditions, operator=operator
        )
        contributions = build_relic_contributions(
            relic_ids, relic_conditions, operator=operator, equivalent_grade=equivalent_grade
        )
        result["relic_contributions"] = contributions
        mods = relic_mods.merge(cond_mods)

        outer_raw = get_outer_buff(theme_id) if apply_outer_buff else None
        outer_mods = outer_buff_to_modifiers(outer_raw if apply_outer_buff else None)
        manual_mods = manual_bonus_to_modifiers(manual_bonus if isinstance(manual_bonus, dict) else {})

        total = mods.merge(outer_mods).merge(manual_mods)
        total_mods = total

        # 直接乘算：藏品/条件/局外/手填 + 技能参数加算
        direct_atk_pct = total.atk_pct + skill_atk_pct
        combat_atk = base["atk"] * (1.0 + direct_atk_pct) + total.atk_flat
        final_hp = base["hp"] * (1.0 + total.hp_pct + skill_hp_pct)
        final_def = base["def"] * (1.0 + total.def_pct + skill_def_pct)
        final_aspd = base["attack_speed"] + total.aspd + skill_aspd
        final_res = float(base["res"]) * (1.0 + skill_res_pct) + skill_res_flat
        final_interval = attack_interval(base["base_attack_time"], final_aspd)

        all_factor = float(contributions["damage_factors"]["all"]["product"])
        typed_factor = float(contributions["damage_factors"][damage_type]["product"])
        relic_dmg = all_factor * typed_factor - 1.0

        final = {
            "hp": final_hp,
            "atk": combat_atk,
            "def": final_def,
            "res": final_res,
            "attack_speed": final_aspd,
            "base_attack_time": base["base_attack_time"],
            "attack_interval": final_interval,
            "damage_pct": relic_dmg,
            "ignore_def_pct": total.ignore_def_pct,
            "true_damage": total.true_damage,
            "skill_atk_pct": skill_atk_pct,
            "direct_atk_pct": direct_atk_pct,
            "skill_res_flat": skill_res_flat,
            "skill_res_pct": skill_res_pct,
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
                "hp_pct_from_skill": skill_hp_pct,
                "def_pct_from_skill": skill_def_pct,
                "aspd_from_skill": skill_aspd,
                "res_flat_from_skill": skill_res_flat,
                "res_pct_from_skill": skill_res_pct,
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
                f"HP+{module_meta.get('hp')} DEF+{module_meta.get('defense')} "
                f"攻速+{module_meta.get('attack_speed')}"
            )
        pot_note = ""
        if float(base.get("potential_atk_flat") or 0) or float(base.get("potential_hp_flat") or 0):
            pot_note = (
                f"（潜能定值 ATK+{float(base.get('potential_atk_flat') or 0):.0f} "
                f"HP+{float(base.get('potential_hp_flat') or 0):.0f} "
                f"DEF+{float(base.get('potential_def_flat') or 0):.0f}）"
            )
        tal_pct = float(base.get("talent_atk_pct") or 0)
        if tal_pct:
            pot_note += f"（天赋ATK%+{tal_pct:.0%}）"
        steps.append(
            f"2. 养成+模组+潜能/天赋基础 ATK={base['atk']:.2f} HP={base['hp']:.0f} DEF={base['def']:.0f} "
            f"攻速={base['attack_speed']:.1f} 间隔={base_interval:.3f}s{pot_note}"
        )
        steps.append(
            f"3. 直接乘算分项：藏品ATK%={relic_mods.atk_pct:.2%} + 条件ATK%={cond_mods.atk_pct:.2%} "
            f"+ 局外ATK%={outer_mods.atk_pct:.2%} + 手填ATK%={manual_mods.atk_pct:.2%} "
            f"+ 技能ATK%={skill_atk_pct:.2%} = {direct_atk_pct:.2%}；"
            f"固定ATK+={total.atk_flat:.1f}"
        )
        steps.append(
            f"4. 战斗面板 ATK = {base['atk']:.2f} × (1+{direct_atk_pct:.4f}) + {total.atk_flat:.1f} "
            f"= {combat_atk:.2f}；HP={final_hp:.0f} DEF={final_def:.0f} 法抗={final_res:.1f} 攻速={final_aspd:.1f}"
        )

    if result["relic_contributions"] is None:
        result["relic_contributions"] = build_relic_contributions(
            relic_ids, relic_conditions, operator=None, equivalent_grade=equivalent_grade
        )

    if enemy_id:
        # 原始面板（无难度修正）
        enemy_raw = gdb.get_enemy_row(
            enemy_id,
            level=enemy_level_index,
            theme_id=None,
            equivalent_grade=0,
        )
        if not enemy_raw:
            raise ValueError(f"未找到敌人: {enemy_id}")
        raw_attrs = dict(enemy_raw.get("attributes") or {})

        # 难度修正后面板
        enemy = gdb.get_enemy_row(
            enemy_id,
            level=enemy_level_index,
            theme_id=theme_id,
            equivalent_grade=equivalent_grade,
        )
        attrs = dict(enemy.get("attributes") or {}) if enemy else raw_attrs

        emods = build_enemy_relic_modifiers(
            relic_ids=relic_ids, equivalent_grade=equivalent_grade,
            relic_conditions=relic_conditions, operator=operator if op_id else None,
        )

        # 敌人手填/技能减益面板修正
        em = enemy_manual if isinstance(enemy_manual, dict) else {}
        man_hp_pct = float(em.get("hp_pct") or 0)
        man_hp_flat = float(em.get("hp_flat") or 0)
        man_atk_pct = float(em.get("atk_pct") or 0)
        man_atk_flat = float(em.get("atk_flat") or 0)
        man_def_pct = float(em.get("def_pct") or 0)
        man_def_flat = float(em.get("def_flat") or 0)
        man_res_pct = float(em.get("res_pct") or 0)
        man_res_flat = float(em.get("res_flat") or 0)

        enemy_base = {
            "hp": float(raw_attrs.get("hp") or 0),
            "atk": float(raw_attrs.get("atk") or 0),
            "def": float(raw_attrs.get("def") or 0),
            "magic_resistance": float(raw_attrs.get("magic_resistance") or 0),
            "attack_speed": float(raw_attrs.get("attack_speed") or 0),
            "move_speed": float(raw_attrs.get("move_speed") or 0),
            "range_radius": float(raw_attrs.get("range_radius") or 0),
            "damage_type": raw_attrs.get("damage_type"),
        }
        enemy_diff = {
            "hp": float(attrs.get("hp") or 0),
            "atk": float(attrs.get("atk") or 0),
            "def": float(attrs.get("def") or 0),
            "magic_resistance": float(attrs.get("magic_resistance") or 0),
            "attack_speed": float(attrs.get("attack_speed") or 0),
            "move_speed": float(attrs.get("move_speed") or 0),
            "range_radius": float(attrs.get("range_radius") or 0),
            "damage_type": attrs.get("damage_type"),
        }
        # 难度面板 → ×(1+藏品%+手填%) + 手填定值；法抗同理
        enemy_final = {
            "hp": float(attrs.get("hp") or 0) * (1.0 + emods.hp_pct + man_hp_pct) + man_hp_flat,
            "atk": float(attrs.get("atk") or 0) * (1.0 + emods.atk_pct + man_atk_pct) + man_atk_flat,
            "def": float(attrs.get("def") or 0) * (1.0 + emods.def_pct + man_def_pct) + man_def_flat,
            "magic_resistance": (
                float(attrs.get("magic_resistance") or 0) * (1.0 + man_res_pct)
                + emods.res_flat
                + man_res_flat
            ),
            "attack_speed": float(attrs.get("attack_speed") or 0) + emods.aspd,
            "move_speed": float(attrs.get("move_speed") or 0),
            "range_radius": float(attrs.get("range_radius") or 0),
            "damage_type": attrs.get("damage_type"),
        }
        result["enemy"] = {
            "id": (enemy or enemy_raw).get("id"),
            "name": (enemy or enemy_raw).get("name"),
            "enemy_level": (enemy or enemy_raw).get("enemy_level"),
            "level_index": (enemy or enemy_raw).get("level_index"),
        }
        result["enemy_base_panel"] = enemy_base
        result["enemy_diff_panel"] = enemy_diff
        result["enemy_final_panel"] = enemy_final
        result["bonus"]["enemy_hp_pct_from_relics"] = emods.hp_pct
        result["bonus"]["enemy_atk_pct_from_relics"] = emods.atk_pct
        result["bonus"]["enemy_def_pct_from_relics"] = emods.def_pct
        result["bonus"]["enemy_aspd_from_relics"] = emods.aspd
        result["bonus"]["enemy_res_flat_from_relics"] = emods.res_flat
        result["bonus"]["enemy_hp_pct_manual"] = man_hp_pct
        result["bonus"]["enemy_atk_pct_manual"] = man_atk_pct
        result["bonus"]["enemy_def_pct_manual"] = man_def_pct
        result["bonus"]["enemy_res_pct_manual"] = man_res_pct
        result["bonus"]["enemy_hp_flat_manual"] = man_hp_flat
        result["bonus"]["enemy_atk_flat_manual"] = man_atk_flat
        result["bonus"]["enemy_def_flat_manual"] = man_def_flat
        result["bonus"]["enemy_res_flat_manual"] = man_res_flat
        result["bonus"]["enemy_difficulty_mods"] = enemy.get("difficulty_mods") or [] if enemy else []
        diff_taken = (enemy or {}).get("damage_taken") or {}
        result["bonus"]["enemy_damage_taken_phys_pct"] = float(diff_taken.get("phys") or 0)
        result["bonus"]["enemy_damage_taken_arts_pct"] = float(diff_taken.get("arts") or 0)

        steps.append("—— 敌人面板 ——")
        steps.append(
            f"敌人「{(enemy or enemy_raw).get('name')}」最终 "
            f"HP={enemy_final['hp']:.0f} DEF={enemy_final['def']:.0f} "
            f"RES={enemy_final['magic_resistance']:.1f}"
        )
        if man_def_pct or man_res_pct or man_res_flat or man_atk_pct or man_hp_pct:
            steps.append(
                f"敌人手填/技能减益：DEF%{man_def_pct:+.0%} RES%{man_res_pct:+.0%} "
                f"RES定值{man_res_flat:+.1f} ATK%{man_atk_pct:+.0%} HP%{man_hp_pct:+.0%}"
            )
        if diff_taken.get("phys") or diff_taken.get("arts"):
            steps.append(
                f"难度受伤修正：物伤加深{float(diff_taken.get('phys') or 0):+.0%} "
                f"法伤加深{float(diff_taken.get('arts') or 0):+.0%}"
            )

    # 干员+敌人 → 单次伤害
    if op_id and enemy_final is not None and combat_atk > 0:
        relic_dmg = 0.0
        ignore = 0.0
        true_dmg = False
        if total_mods is not None:
            relic_dmg = float((result.get("final_panel") or {}).get("damage_pct") or 0)
            ignore = float(total_mods.ignore_def_pct or 0)
            true_dmg = bool(total_mods.true_damage)

        # 合并难度「受到伤害降低/提升」到结算乘区
        merged_enemy_manual = dict(enemy_manual) if isinstance(enemy_manual, dict) else {}
        diff_taken = (result.get("bonus") or {})
        merged_enemy_manual["phys_damage_taken_pct"] = float(
            merged_enemy_manual.get("phys_damage_taken_pct") or 0
        ) + float(diff_taken.get("enemy_damage_taken_phys_pct") or 0)
        merged_enemy_manual["arts_damage_taken_pct"] = float(
            merged_enemy_manual.get("arts_damage_taken_pct") or 0
        ) + float(diff_taken.get("enemy_damage_taken_arts_pct") or 0)

        hit_info = resolve_hit_from_panels(
            combat_atk,
            damage_type=damage_type,  # type: ignore[arg-type]
            enemy_def=float(enemy_final["def"]),
            enemy_res=float(enemy_final["magic_resistance"]),
            skill_manual=skill_manual,
            enemy_manual=merged_enemy_manual,
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
