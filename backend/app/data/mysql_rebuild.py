"""MySQL 全量导入与局部刷新。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import text

from app.combat.attributes import skill_multiplier_and_duration
from app.data.difficulty_rules import parse_rule_desc_mods
from app.data.mysql_core import _lock, db_counts, get_engine, init_schema

def _clear_all(conn) -> None:
    # FK order
    tables = [
        "operator_skill_levels",
        "operator_skills",
        "operator_talents",
        "operator_potential_buffs",
        "relic_condition_params",
        "relic_effect_rules",
        "theme_outer_buffs",
        "relic_effects",
        "relic_upgrade_steps",
        "relic_upgrade_groups",
        "difficulty_stat_mods",
        "theme_difficulties",
        "theme_enemies",
        "module_levels",
        "modules",
        "operator_favor_stats",
        "operator_phase_stats",
        "operator_phases",
        "operators",
        "enemy_levels",
        "enemies",
        "relics",
        "themes",
        "meta",
    ]
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    for t in tables:
        conn.execute(text(f"TRUNCATE TABLE {t}"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def _frame_data(frame: dict) -> dict[str, float]:
    data = frame.get("data") or {}
    return {
        "hp": float(data.get("maxHp") or 0),
        "atk": float(data.get("atk") or 0),
        "def_stat": float(data.get("def") or 0),
        "res": float(data.get("magicResistance") or 0),
        "aspd": float(data.get("attackSpeed") or 100),
        "base_attack_time": float(data.get("baseAttackTime") or 1),
    }


def _skill_level_row(
    operator_id: str,
    skill_id: str,
    level_index: int,
    level_data: dict,
) -> dict[str, Any]:
    """把一档原始技能数据转换为可直接写入 MySQL 的行。"""
    info = skill_multiplier_and_duration([level_data], 1)
    sp_data = level_data.get("sp_data") or level_data.get("spData") or {}
    parsed = {
        key: info[key]
        for key in (
            "atk_scale",
            "atk_pct",
            "attack_speed",
            "base_attack_time",
            "damage_scale",
            "secondary_scale",
            "cnt",
            "hp_pct",
            "def_pct",
            "res_flat",
            "res_pct",
            "enemy_effects",
        )
    }
    return {
        "operator_id": operator_id,
        "skill_id": skill_id,
        "level": level_index + 1,
        "name": info.get("name"),
        "description": info.get("description") or "",
        "duration": float(info.get("duration") or 0),
        "skill_type": level_data.get("skill_type") or level_data.get("skillType"),
        "prefab_id": level_data.get("prefab") or level_data.get("prefabId"),
        "sp_cost": sp_data.get("spCost"),
        "sp_init": sp_data.get("initSp"),
        "blackboard": json.dumps(level_data.get("blackboard") or [], ensure_ascii=False),
        "sp_data": json.dumps(sp_data, ensure_ascii=False),
        "parsed_effects": json.dumps(parsed, ensure_ascii=False),
    }


_parse_rule_desc_mods = parse_rule_desc_mods


def rebuild_from_store(store: Any) -> dict[str, int]:
    """从 GameDataStore 全量重建 MySQL。"""
    with _lock:
        init_schema()
        eng = get_engine()
        with eng.begin() as conn:
            approved_rules = [dict(r) for r in conn.execute(text(
                "SELECT * FROM relic_effect_rules WHERE review_status='approved'"
            )).mappings().all()]
            approved_params = [dict(r) for r in conn.execute(text(
                "SELECT * FROM relic_condition_params WHERE review_status='approved'"
            )).mappings().all()]
            approved_outer = [dict(r) for r in conn.execute(text(
                "SELECT * FROM theme_outer_buffs WHERE review_status='approved'"
            )).mappings().all()]
            _clear_all(conn)

            # themes
            topics = (store.roguelike_topic_table.get("topics") or {})
            details = (store.roguelike_topic_table.get("details") or {})
            theme_ids = set(topics.keys()) | set(details.keys())
            for tid in sorted(theme_ids):
                t = topics.get(tid) or {}
                conn.execute(
                    text("INSERT INTO themes(id,name,start_time) VALUES(:id,:name,:st)"),
                    {"id": tid, "name": t.get("name") or tid, "st": t.get("startTime")},
                )

            # difficulties + mods
            for tid, detail in details.items():
                if not isinstance(detail, dict):
                    continue
                for d in detail.get("difficulties") or []:
                    if not isinstance(d, dict):
                        continue
                    eq = int(d.get("equivalentGrade") or d.get("grade") or 0)
                    conn.execute(
                        text(
                            """
                            INSERT INTO theme_difficulties(
                              theme_id,mode_difficulty,grade,equivalent_grade,name,score_factor,rule_desc,color,sort_id
                            ) VALUES (
                              :theme_id,:mode_difficulty,:grade,:equivalent_grade,:name,:score_factor,:rule_desc,:color,:sort_id
                            )
                            """
                        ),
                        {
                            "theme_id": tid,
                            "mode_difficulty": d.get("modeDifficulty") or "NORMAL",
                            "grade": int(d.get("grade") or 0),
                            "equivalent_grade": eq,
                            "name": d.get("name") or "",
                            "score_factor": d.get("scoreFactor"),
                            "rule_desc": d.get("ruleDesc") or "",
                            "color": d.get("color"),
                            "sort_id": d.get("sortId"),
                        },
                    )
                    for mod in _parse_rule_desc_mods(tid, eq, d.get("ruleDesc") or ""):
                        conn.execute(
                            text(
                                """
                                INSERT INTO difficulty_stat_mods(theme_id,equivalent_grade,target,attr,value,op,note)
                                VALUES(:theme_id,:equivalent_grade,:target,:attr,:value,:op,:note)
                                ON DUPLICATE KEY UPDATE value=VALUES(value), op=VALUES(op), note=VALUES(note)
                                """
                            ),
                            mod,
                        )

                # upgrade groups
                for gid, g in (detail.get("difficultyUpgradeRelicGroups") or {}).items():
                    if not isinstance(g, dict):
                        continue
                    rd = g.get("relicData") or []
                    base_id = rd[0].get("relicId") if rd else None
                    conn.execute(
                        text(
                            "INSERT INTO relic_upgrade_groups(group_id,theme_id,base_relic_id) VALUES(:g,:t,:b)"
                        ),
                        {"g": gid, "t": tid, "b": base_id},
                    )
                    for step in rd:
                        if not isinstance(step, dict):
                            continue
                        conn.execute(
                            text(
                                """
                                INSERT INTO relic_upgrade_steps(group_id,equivalent_grade_min,relic_id)
                                VALUES(:g,:eq,:rid)
                                """
                            ),
                            {
                                "g": gid,
                                "eq": int(step.get("equivalentGrade") or 0),
                                "rid": step.get("relicId"),
                            },
                        )

            # operators
            op_count = 0
            skill_count = 0
            skill_level_count = 0
            for brief in store.list_operators(limit=20000):
                detail = store.get_operator(brief["id"])
                if not detail:
                    continue
                raw = store.character_table.get(brief["id"]) or {}
                conn.execute(
                    text(
                        """
                        INSERT INTO operators(id,name,rarity,profession,profession_cn,sub_profession,position,appellation,description)
                        VALUES(:id,:name,:rarity,:profession,:profession_cn,:sub_profession,:position,:appellation,:description)
                        """
                    ),
                    {
                        "id": brief["id"],
                        "name": brief["name"],
                        "rarity": brief.get("rarity") or 0,
                        "profession": brief.get("profession"),
                        "profession_cn": brief.get("profession_cn"),
                        "sub_profession": brief.get("sub_profession"),
                        "position": brief.get("position"),
                        "appellation": raw.get("appellation") or "",
                        "description": detail.get("description") or "",
                    },
                )
                for i, ph in enumerate(raw.get("phases") or []):
                    frames = ph.get("attributesKeyFrames") or []
                    max_lv = frames[-1]["level"] if frames else 1
                    conn.execute(
                        text(
                            """
                            INSERT INTO operator_phases(operator_id,elite,max_level,range_id)
                            VALUES(:oid,:elite,:max_level,:range_id)
                            """
                        ),
                        {"oid": brief["id"], "elite": i, "max_level": max_lv, "range_id": ph.get("rangeId")},
                    )
                    # 仅存 keyFrames 端点
                    for fr in frames:
                        fd = _frame_data(fr)
                        conn.execute(
                            text(
                                """
                                INSERT INTO operator_phase_stats(
                                  operator_id,elite,level,hp,atk,def_stat,res,aspd,base_attack_time
                                ) VALUES (
                                  :oid,:elite,:level,:hp,:atk,:def_stat,:res,:aspd,:bat
                                )
                                """
                            ),
                            {
                                "oid": brief["id"],
                                "elite": i,
                                "level": int(fr.get("level") or 1),
                                **fd,
                                "bat": fd["base_attack_time"],
                            },
                        )
                for fr in raw.get("favorKeyFrames") or []:
                    data = fr.get("data") or {}
                    conn.execute(
                        text(
                            """
                            INSERT INTO operator_favor_stats(operator_id,favor_level,hp,atk,def_stat)
                            VALUES(:oid,:lv,:hp,:atk,:def_stat)
                            """
                        ),
                        {
                            "oid": brief["id"],
                            "lv": int(fr.get("level") or 0),
                            "hp": float(data.get("maxHp") or 0),
                            "atk": float(data.get("atk") or 0),
                            "def_stat": float(data.get("def") or 0),
                        },
                    )
                # 技能：保留原始字段，并将常用面板/伤害字段预解析后入库。
                for skill_index, skill in enumerate(detail.get("skills") or []):
                    skill_id = skill.get("skill_id")
                    levels = skill.get("levels") or []
                    if not skill_id or not levels:
                        continue
                    unlock = skill.get("unlock") or {}
                    phase = str(unlock.get("phase") or "")
                    unlock_elite = 2 if phase.endswith("2") else 1 if phase.endswith("1") else 0
                    conn.execute(
                        text(
                            """
                            INSERT INTO operator_skills(
                              operator_id,skill_id,skill_index,unlock_elite,unlock_level,max_level
                            ) VALUES(:operator_id,:skill_id,:skill_index,:unlock_elite,:unlock_level,:max_level)
                            """
                        ),
                        {
                            "operator_id": brief["id"],
                            "skill_id": skill_id,
                            "skill_index": skill_index,
                            "unlock_elite": unlock_elite,
                            "unlock_level": int(unlock.get("level") or 1),
                            "max_level": len(levels),
                        },
                    )
                    skill_count += 1
                    for level_index, level_data in enumerate(levels):
                        conn.execute(
                            text(
                                """
                                INSERT INTO operator_skill_levels(
                                  operator_id,skill_id,level,name,description,duration,skill_type,
                                  prefab_id,sp_cost,sp_init,blackboard,sp_data,parsed_effects
                                ) VALUES(
                                  :operator_id,:skill_id,:level,:name,:description,:duration,:skill_type,
                                  :prefab_id,:sp_cost,:sp_init,CAST(:blackboard AS JSON),
                                  CAST(:sp_data AS JSON),CAST(:parsed_effects AS JSON)
                                )
                                """
                            ),
                            _skill_level_row(brief["id"], skill_id, level_index, level_data),
                        )
                        skill_level_count += 1
                for mod in detail.get("modules") or []:
                    levels = mod.get("levels") or []
                    conn.execute(
                        text(
                            """
                            INSERT INTO modules(id,operator_id,name,type_name,max_level,description)
                            VALUES(:id,:oid,:name,:type_name,:max_level,:description)
                            """
                        ),
                        {
                            "id": mod["id"],
                            "oid": brief["id"],
                            "name": mod.get("name") or mod["id"],
                            "type_name": mod.get("type"),
                            "max_level": len(levels) or 1,
                            "description": mod.get("description") or "",
                        },
                    )
                    for lv in levels:
                        conn.execute(
                            text(
                                """
                                INSERT INTO module_levels(module_id,level,atk,atk_pct,hp,defense,attack_speed,trait_effects,talent_effects)
                                VALUES(:mid,:level,:atk,:atk_pct,:hp,:defense,:attack_speed,CAST(:trait_effects AS JSON),CAST(:talent_effects AS JSON))
                                """
                            ),
                            {
                                "mid": mod["id"],
                                "level": int(lv.get("level") or 1),
                                "atk": float(lv.get("atk") or 0),
                                "atk_pct": float(lv.get("atk_pct") or 0),
                                "hp": float(lv.get("hp") or 0),
                                "defense": float(lv.get("defense") or 0),
                                "attack_speed": float(lv.get("attack_speed") or 0),
                                "trait_effects": json.dumps(lv.get("trait_effects") or [], ensure_ascii=False),
                                "talent_effects": json.dumps(lv.get("talent_effects") or [], ensure_ascii=False),
                            },
                        )
                # talents（含精英解锁档，避免同潜能不同精英互相覆盖）
                for ti, talent in enumerate(raw.get("talents") or []):
                    for cand in talent.get("candidates") or []:
                        bb = cand.get("blackboard") or []
                        if isinstance(bb, list) and bb:
                            try:
                                bb_json = json.dumps(bb, ensure_ascii=False)
                            except Exception:
                                bb_json = None
                        else:
                            bb_json = None
                        unlock = cand.get("unlockCondition") or {}
                        phase = str(unlock.get("phase") or "")
                        if phase.endswith("2") or phase == "PHASE_2":
                            unlock_elite = 2
                        elif phase.endswith("1") or phase == "PHASE_1":
                            unlock_elite = 1
                        else:
                            unlock_elite = 0
                        conn.execute(
                            text(
                                """
                                INSERT IGNORE INTO operator_talents(
                                  operator_id,talent_index,unlock_elite,name,description,potential_rank,blackboard
                                ) VALUES(:oid,:ti,:ue,:name,:desc,:pr,:bb)
                                """
                            ),
                            {
                                "oid": brief["id"],
                                "ti": ti,
                                "ue": unlock_elite,
                                "name": cand.get("name") or "",
                                "desc": cand.get("description") or "",
                                "pr": int(cand.get("requiredPotentialRank") or 0),
                                "bb": bb_json,
                            },
                        )
                # potentialRanks → 定值面板加成
                for ri, pr in enumerate(raw.get("potentialRanks") or []):
                    if not isinstance(pr, dict):
                        continue
                    buff = ((pr.get("buff") or {}).get("attributes") or {})
                    for mod in buff.get("attributeModifiers") or []:
                        if not isinstance(mod, dict):
                            continue
                        formula = str(mod.get("formulaItem") or "ADDITION").upper()
                        if formula not in ("ADDITION", "FINAL_ADDITION"):
                            continue
                        at = str(mod.get("attributeType") or "").upper()
                        attr_map = {
                            "MAX_HP": "hp",
                            "HP": "hp",
                            "ATK": "atk",
                            "DEF": "def",
                            "ATTACK_SPEED": "aspd",
                            "ATTACKSPEED": "aspd",
                            "MAGIC_RESISTANCE": "res",
                            "MAGICRESISTANCE": "res",
                        }
                        attr = attr_map.get(at)
                        if not attr:
                            continue
                        conn.execute(
                            text(
                                """
                                INSERT INTO operator_potential_buffs(operator_id,rank_index,attr,value)
                                VALUES(:oid,:ri,:attr,:val)
                                ON DUPLICATE KEY UPDATE value=VALUES(value)
                                """
                            ),
                            {
                                "oid": brief["id"],
                                "ri": ri,
                                "attr": attr,
                                "val": float(mod.get("value") or 0),
                            },
                        )
                op_count += 1

            # enemies
            en_count = 0
            for brief in store.list_enemies(limit=50000):
                # 取 0 档属性作为默认 damage_type
                detail0 = store.get_enemy(brief["id"], level=0) or {}
                attrs0 = detail0.get("attributes") or {}
                conn.execute(
                    text(
                        """
                        INSERT INTO enemies(id,name,enemy_level,description,damage_type)
                        VALUES(:id,:name,:enemy_level,:description,:damage_type)
                        """
                    ),
                    {
                        "id": brief["id"],
                        "name": brief["name"],
                        "enemy_level": brief.get("enemy_level"),
                        "description": brief.get("description") or "",
                        "damage_type": attrs0.get("damage_type"),
                    },
                )
                # 所有 level_index
                n = int(detail0.get("raw_level_count") or 1)
                for li in range(max(1, n)):
                    d = store.get_enemy(brief["id"], level=li) or {}
                    a = d.get("attributes") or {}
                    if not a and li > 0:
                        break
                    conn.execute(
                        text(
                            """
                            INSERT INTO enemy_levels(
                              enemy_id,level_index,hp,atk,def_stat,magic_resistance,move_speed,attack_speed,range_radius
                            ) VALUES (
                              :eid,:li,:hp,:atk,:def_stat,:mr,:ms,:aspd,:rr
                            )
                            """
                        ),
                        {
                            "eid": brief["id"],
                            "li": li,
                            "hp": float(a.get("hp") or 0),
                            "atk": float(a.get("atk") or 0),
                            "def_stat": float(a.get("def") or 0),
                            "mr": float(a.get("magic_resistance") or 0),
                            "ms": float(a.get("move_speed") or 0),
                            "aspd": float(a.get("attack_speed") or 0),
                            "rr": float(a.get("range_radius") or 0),
                        },
                    )
                en_count += 1

            # relics + effects
            from app.combat.relics import (
                EnemyStatModifiers,
                load_relic_patches,
                modifiers_from_patch,
                parse_enemy_relic_text,
                parse_relic_text,
            )

            patches = load_relic_patches()
            relic_count = 0
            effect_count = 0
            for r in store.relics:
                tid = r.get("theme") or ""
                if tid not in theme_ids:
                    # 保底主题
                    conn.execute(
                        text("INSERT IGNORE INTO themes(id,name,start_time) VALUES(:id,:name,NULL)"),
                        {"id": tid, "name": tid},
                    )
                    theme_ids.add(tid)
                rid = r["id"]
                # find item type from raw
                detail_raw = (details.get(tid) or {}).get("items", {}).get(rid) or {}
                conn.execute(
                    text(
                        """
                        INSERT INTO relics(id,theme_id,name,usage_text,description,icon_id,order_id,item_type)
                        VALUES(:id,:theme_id,:name,:usage_text,:description,:icon_id,:order_id,:item_type)
                        """
                    ),
                    {
                        "id": rid,
                        "theme_id": tid,
                        "name": r.get("name") or rid,
                        "usage_text": r.get("usage") or "",
                        "description": r.get("description") or "",
                        "icon_id": r.get("icon_id") or rid,
                        "order_id": str(r.get("order_id") or ""),
                        "item_type": str(detail_raw.get("type") or "RELIC"),
                    },
                )
                # effects: manual patch > parsed（干员 + 敌人）
                if rid in patches and not str(rid).startswith("example_"):
                    mod = modifiers_from_patch(patches[rid])
                    enemy_mod = EnemyStatModifiers()
                    source = "manual"
                else:
                    mod = parse_relic_text(r.get("name") or "", r.get("usage") or "")
                    enemy_mod = parse_enemy_relic_text(r.get("name") or "", r.get("usage") or "")
                    source = "parsed"
                attr_map = {
                    "atk_pct": mod.atk_pct,
                    "atk_flat": mod.atk_flat,
                    "damage_pct": mod.damage_pct,
                    "aspd": mod.aspd,
                    "ignore_def_pct": mod.ignore_def_pct,
                    "phys_damage_pct": mod.phys_damage_pct,
                    "arts_damage_pct": mod.arts_damage_pct,
                    "hp_pct": mod.hp_pct,
                    "def_pct": mod.def_pct,
                }
                for attr, val in attr_map.items():
                    if not val:
                        continue
                    conn.execute(
                        text(
                            """
                            INSERT INTO relic_effects(relic_id,target,attr,value,source,note)
                            VALUES(:rid,'operator',:attr,:value,:source,:note)
                            """
                        ),
                        {"rid": rid, "attr": attr, "value": float(val), "source": source, "note": ";".join(mod.notes[:3])},
                    )
                    effect_count += 1
                if mod.true_damage:
                    conn.execute(
                        text(
                            """
                            INSERT INTO relic_effects(relic_id,target,attr,value,source,note)
                            VALUES(:rid,'operator','true_damage',1,:source,:note)
                            """
                        ),
                        {"rid": rid, "source": source, "note": "true_damage"},
                    )
                    effect_count += 1
                enemy_attr_map = {
                    "hp_pct": enemy_mod.hp_pct,
                    "atk_pct": enemy_mod.atk_pct,
                    "def_pct": enemy_mod.def_pct,
                    "aspd": enemy_mod.aspd,
                    "res_flat": enemy_mod.res_flat,
                }
                for attr, val in enemy_attr_map.items():
                    if not val:
                        continue
                    conn.execute(
                        text(
                            """
                            INSERT INTO relic_effects(relic_id,target,attr,value,source,note)
                            VALUES(:rid,'enemy',:attr,:value,:source,:note)
                            """
                        ),
                        {
                            "rid": rid,
                            "attr": attr,
                            "value": float(val),
                            "source": source,
                            "note": ";".join(enemy_mod.notes[:3]),
                        },
                    )
                    effect_count += 1
                relic_count += 1

            # theme enemy pools（依赖本地关卡 JSON，缺失时尽量下载）
            from app.data.theme_enemy_sync import extract_theme_enemy_ids, iter_theme_details

            te_count = 0
            for tid, detail in iter_theme_details(store.roguelike_topic_table):
                ids = extract_theme_enemy_ids(tid, detail, download_missing=True, max_workers=6)
                for eid in ids:
                    exists = conn.execute(
                        text("SELECT 1 FROM enemies WHERE id=:id"), {"id": eid}
                    ).first()
                    if not exists:
                        continue
                    conn.execute(
                        text(
                            "INSERT IGNORE INTO theme_enemies(theme_id,enemy_id) VALUES(:tid,:eid)"
                        ),
                        {"tid": tid, "eid": eid},
                    )
                    te_count += 1

            # Restore curated rules after catalog rebuild; parsed rows can be
            # regenerated, but approved manual decisions must never be lost.
            for row in approved_rules:
                row.pop("id", None)
                if conn.execute(text("SELECT 1 FROM relics WHERE id=:id"), {"id": row["relic_id"]}).first():
                    conn.execute(text("""
                      INSERT INTO relic_effect_rules(relic_id,target,attr,operation,value,value_expr,when_param,damage_type,
                        calculation_status,ignored_reason,source,rule_version,review_status,display_order,note,reviewed_at)
                      VALUES(:relic_id,:target,:attr,:operation,:value,:value_expr,:when_param,:damage_type,
                        :calculation_status,:ignored_reason,:source,:rule_version,:review_status,:display_order,:note,:reviewed_at)
                    """), row)
            for row in approved_params:
                if conn.execute(text("SELECT 1 FROM relics WHERE id=:id"), {"id": row["relic_id"]}).first():
                    conn.execute(text("""
                      INSERT INTO relic_condition_params(relic_id,param_id,param_type,label,default_value,min_value,max_value,
                        step_value,unit,auto_rule,display_order,rule_version,review_status)
                      VALUES(:relic_id,:param_id,:param_type,:label,:default_value,:min_value,:max_value,
                        :step_value,:unit,:auto_rule,:display_order,:rule_version,:review_status)
                    """), row)
            for row in approved_outer:
                if conn.execute(text("SELECT 1 FROM themes WHERE id=:id"), {"id": row["theme_id"]}).first():
                    conn.execute(text("""
                      INSERT INTO theme_outer_buffs(theme_id,name,atk_pct,hp_pct,def_pct,aspd,note,rule_version,review_status)
                      VALUES(:theme_id,:name,:atk_pct,:hp_pct,:def_pct,:aspd,:note,:rule_version,:review_status)
                    """), row)

            counts = {
                "operators": op_count,
                "operator_skills": skill_count,
                "operator_skill_levels": skill_level_count,
                "enemies": en_count,
                "relics": relic_count,
                "relic_effects": effect_count,
                "theme_enemies": te_count,
            }
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                text(
                    """
                    INSERT INTO meta(k,v) VALUES('rebuilt_at', CAST(:v AS JSON))
                    ON DUPLICATE KEY UPDATE v=CAST(:v AS JSON)
                    """
                ),
                {"v": json.dumps(now)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO meta(k,v) VALUES('counts', CAST(:v AS JSON))
                    ON DUPLICATE KEY UPDATE v=CAST(:v AS JSON)
                    """
                ),
                {"v": json.dumps(counts, ensure_ascii=False)},
            )

        logger.info(f"MySQL rebuilt: {counts}")
        return db_counts()


def refresh_modules_from_store(store: Any) -> dict[str, int]:
    """只刷新模组及等级效果，避免影响藏品规则和其他已审核数据。"""
    with _lock:
        init_schema()
        module_count = 0
        level_count = 0
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM modules"))
            for brief in store.list_operators(limit=20000):
                detail = store.get_operator(brief["id"])
                if not detail:
                    continue
                for mod in detail.get("modules") or []:
                    levels = mod.get("levels") or []
                    conn.execute(
                        text("""
                            INSERT INTO modules(id,operator_id,name,type_name,max_level,description)
                            VALUES(:id,:oid,:name,:type_name,:max_level,:description)
                        """),
                        {
                            "id": mod["id"], "oid": brief["id"],
                            "name": mod.get("name") or mod["id"], "type_name": mod.get("type"),
                            "max_level": len(levels) or 1, "description": mod.get("description") or "",
                        },
                    )
                    module_count += 1
                    for lv in levels:
                        conn.execute(
                            text("""
                                INSERT INTO module_levels(module_id,level,atk,atk_pct,hp,defense,attack_speed,trait_effects,talent_effects)
                                VALUES(:mid,:level,:atk,:atk_pct,:hp,:defense,:attack_speed,CAST(:trait_effects AS JSON),CAST(:talent_effects AS JSON))
                            """),
                            {
                                "mid": mod["id"], "level": int(lv.get("level") or 1),
                                "atk": float(lv.get("atk") or 0), "atk_pct": float(lv.get("atk_pct") or 0),
                                "hp": float(lv.get("hp") or 0), "defense": float(lv.get("defense") or 0),
                                "attack_speed": float(lv.get("attack_speed") or 0),
                                "trait_effects": json.dumps(lv.get("trait_effects") or [], ensure_ascii=False),
                                "talent_effects": json.dumps(lv.get("talent_effects") or [], ensure_ascii=False),
                            },
                        )
                        level_count += 1
        return {"modules": module_count, "module_levels": level_count}



