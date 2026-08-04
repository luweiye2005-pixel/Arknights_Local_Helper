"""MySQL 主库：连接、建表、导入、查询。"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.combat.attributes import skill_multiplier_and_duration
from app.config import REPO_ROOT, settings
from app.data.difficulty_rules import parse_rule_desc_mods

_lock = threading.RLock()
_engine: Engine | None = None


def source_name() -> str:
    return "mysql"

SCHEMA_SQL = (REPO_ROOT / "scripts" / "mysql_init.sql").read_text(encoding="utf-8")


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                url = (
                    f"mysql+pymysql://{quote_plus(settings.MYSQL_USER)}:"
                    f"{quote_plus(settings.MYSQL_PASSWORD)}@"
                    f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/"
                    f"{settings.MYSQL_DATABASE}?charset=utf8mb4"
                )
                _engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
    return _engine


def init_schema() -> None:
    eng = get_engine()
    statements: list[str] = []
    buf: list[str] = []
    for line in SCHEMA_SQL.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        buf.append(line)
        if s.endswith(";"):
            statements.append("\n".join(buf))
            buf = []
    if buf:
        statements.append("\n".join(buf))
    with eng.begin() as conn:
        for stmt in statements:
            if stmt.strip():
                conn.execute(text(stmt))
    ensure_operator_position_column()
    ensure_talent_and_potential_schema()
    ensure_module_effect_schema()


def ensure_module_effect_schema() -> None:
    """兼容旧库：为模组等级补充来自 battle_equip_table 的描述数据。"""
    with get_engine().begin() as conn:
        cols = {r[0] for r in conn.execute(text("SHOW COLUMNS FROM module_levels")).fetchall()}
        if "trait_effects" not in cols:
            conn.execute(text("ALTER TABLE module_levels ADD COLUMN trait_effects JSON NULL"))
        if "talent_effects" not in cols:
            conn.execute(text("ALTER TABLE module_levels ADD COLUMN talent_effects JSON NULL"))


def ensure_talent_and_potential_schema() -> None:
    """兼容旧库：天赋表补 unlock_elite，并确保潜能定值表存在。"""
    eng = get_engine()
    with eng.begin() as conn:
        tables = {r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()}
        if "operator_potential_buffs" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS operator_potential_buffs (
                      operator_id VARCHAR(64) NOT NULL,
                      rank_index TINYINT NOT NULL,
                      attr VARCHAR(32) NOT NULL,
                      value DOUBLE NOT NULL DEFAULT 0,
                      PRIMARY KEY (operator_id, rank_index, attr),
                      CONSTRAINT fk_pot_op FOREIGN KEY (operator_id) REFERENCES operators(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            )
        if "operator_talents" not in tables:
            return
        cols = {r[0] for r in conn.execute(text("SHOW COLUMNS FROM operator_talents")).fetchall()}
        if "unlock_elite" in cols:
            return
        # 旧主键不含 unlock_elite：重建空表结构（数据需 rebuild）
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        conn.execute(text("DROP TABLE IF EXISTS operator_talents"))
        conn.execute(
            text(
                """
                CREATE TABLE operator_talents (
                  operator_id VARCHAR(64) NOT NULL,
                  talent_index INT NOT NULL DEFAULT 0,
                  unlock_elite TINYINT NOT NULL DEFAULT 0,
                  name VARCHAR(128) NOT NULL DEFAULT '',
                  description TEXT NULL,
                  potential_rank INT NOT NULL DEFAULT 0,
                  blackboard JSON NULL,
                  PRIMARY KEY (operator_id, talent_index, unlock_elite, potential_rank),
                  CONSTRAINT fk_talent_op FOREIGN KEY (operator_id) REFERENCES operators(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        logger.warning("已重建 operator_talents 表结构（含 unlock_elite），请执行 rebuild-db")


def ensure_operator_position_column() -> None:
    """已有库补 position 列，并从 character_table 回填。"""
    eng = get_engine()
    with eng.begin() as conn:
        cols = {
            r[0]
            for r in conn.execute(text("SHOW COLUMNS FROM operators")).fetchall()
        }
        if "position" not in cols:
            conn.execute(text("ALTER TABLE operators ADD COLUMN position VARCHAR(16) NULL"))
    # 回填空值
    try:
        from app.data.store import get_store

        store = get_store()
        updates = []
        for brief in store.list_operators(limit=20000):
            pos = brief.get("position")
            if pos:
                updates.append({"id": brief["id"], "position": pos})
        if not updates:
            return
        with eng.begin() as conn:
            for u in updates:
                conn.execute(
                    text("UPDATE operators SET position=:position WHERE id=:id AND (position IS NULL OR position='')"),
                    u,
                )
    except Exception as e:
        logger.warning(f"回填 operators.position 失败: {e}")


def set_meta(key: str, value: Any) -> None:
    payload = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    with get_engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO meta(k, v) VALUES(:k, CAST(:v AS JSON))
                ON DUPLICATE KEY UPDATE v=CAST(:v AS JSON)
                """
            ),
            {"k": key, "v": payload if payload.startswith("{") or payload.startswith("[") else json.dumps(payload)},
        )


def get_meta(key: str, default: Any = None) -> Any:
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT v FROM meta WHERE k=:k"), {"k": key}).mappings().first()
        if not row:
            return default
        v = row["v"]
        if isinstance(v, (dict, list)):
            return v
        try:
            return json.loads(v)
        except Exception:
            return v


def db_counts() -> dict[str, int]:
    init_schema()
    with get_engine().connect() as conn:
        def cnt(table: str) -> int:
            return int(conn.execute(text(f"SELECT COUNT(*) AS c FROM {table}")).scalar() or 0)

        return {
            "operators": cnt("operators"),
            "operator_skills": cnt("operator_skills"),
            "operator_skill_levels": cnt("operator_skill_levels"),
            "enemies": cnt("enemies"),
            "relics": cnt("relics"),
            "modules": cnt("modules"),
            "themes": cnt("themes"),
            "theme_difficulties": cnt("theme_difficulties"),
            "theme_enemies": cnt("theme_enemies"),
            "relic_effects": cnt("relic_effects"),
        }


def db_dsn_display() -> str:
    return f"{settings.MYSQL_USER}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"


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


# ---------- queries ----------

def search_operators(q: str | None = None, limit: int = 50) -> list[dict]:
    init_schema()
    sql = """
        SELECT id,name,rarity,profession,profession_cn,sub_profession,position
        FROM operators
    """
    params: dict[str, Any] = {"limit": limit}
    if q and q.strip():
        sql += " WHERE name LIKE :like OR id LIKE :like OR appellation LIKE :like OR profession_cn LIKE :like"
        params["like"] = f"%{q.strip()}%"
    sql += " ORDER BY rarity DESC, name ASC LIMIT :limit"
    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            pos = (d.get("position") or "").upper() or None
            d["position"] = pos
            d["position_cn"] = {"MELEE": "近战", "RANGED": "远程"}.get(pos or "", pos)
            out.append(d)
        return out


def get_operator_detail(operator_id: str) -> dict | None:
    init_schema()
    with get_engine().connect() as conn:
        op = conn.execute(text("SELECT * FROM operators WHERE id=:id"), {"id": operator_id}).mappings().first()
        if not op:
            return None
        phases_rows = conn.execute(
            text("SELECT elite,max_level,range_id FROM operator_phases WHERE operator_id=:id ORDER BY elite"),
            {"id": operator_id},
        ).mappings().all()
        phases = []
        raw_phases = []
        for ph in phases_rows:
            elite = int(ph["elite"])
            stats = conn.execute(
                text(
                    """
                    SELECT level,hp,atk,def_stat,res,aspd,base_attack_time
                    FROM operator_phase_stats
                    WHERE operator_id=:id AND elite=:elite ORDER BY level
                    """
                ),
                {"id": operator_id, "elite": elite},
            ).mappings().all()
            frames = [
                {
                    "level": int(s["level"]),
                    "data": {
                        "maxHp": float(s["hp"]),
                        "atk": float(s["atk"]),
                        "def": float(s["def_stat"]),
                        "magicResistance": float(s["res"]),
                        "attackSpeed": float(s["aspd"]),
                        "baseAttackTime": float(s["base_attack_time"]),
                    },
                }
                for s in stats
            ]
            phases.append({"elite": elite, "max_level": int(ph["max_level"]), "range_id": ph["range_id"]})
            raw_phases.append({"attributesKeyFrames": frames, "rangeId": ph["range_id"]})

        favor_rows = conn.execute(
            text("SELECT favor_level,hp,atk,def_stat FROM operator_favor_stats WHERE operator_id=:id ORDER BY favor_level"),
            {"id": operator_id},
        ).mappings().all()
        favor_key_frames = [
            {
                "level": int(f["favor_level"]),
                "data": {"maxHp": float(f["hp"]), "atk": float(f["atk"]), "def": float(f["def_stat"])},
            }
            for f in favor_rows
        ]

        mods = conn.execute(
            text("SELECT id,name,type_name,max_level,description FROM modules WHERE operator_id=:id"),
            {"id": operator_id},
        ).mappings().all()
        modules = []
        for m in mods:
            levels = conn.execute(
                text(
                    """
                    SELECT level,atk,atk_pct,hp,defense,attack_speed,trait_effects,talent_effects
                    FROM module_levels WHERE module_id=:mid ORDER BY level
                    """
                ),
                {"mid": m["id"]},
            ).mappings().all()
            modules.append(
                {
                    "id": m["id"],
                    "name": m["name"],
                    "type": m["type_name"],
                    "description": m["description"],
                    "max_level": int(m["max_level"] or 1),
                    "levels": [_module_level_dict(lv) for lv in levels],
                }
            )

        # talents
        talents_rows = conn.execute(
            text(
                """
                SELECT talent_index,unlock_elite,name,description,potential_rank,blackboard
                FROM operator_talents WHERE operator_id=:id
                ORDER BY talent_index, unlock_elite, potential_rank
                """
            ),
            {"id": operator_id},
        ).mappings().all()
        talents_out: list[dict] = []
        for t in talents_rows:
            bb = t["blackboard"]
            if isinstance(bb, str):
                try:
                    bb = json.loads(bb)
                except Exception:
                    bb = None
            talents_out.append({
                "index": int(t["talent_index"]),
                "unlock_elite": int(t.get("unlock_elite") or 0),
                "name": t["name"],
                "description": t["description"],
                "potential_rank": int(t["potential_rank"] or 0),
                "blackboard": bb,
            })

        pot_rows = conn.execute(
            text(
                """
                SELECT rank_index, attr, value FROM operator_potential_buffs
                WHERE operator_id=:id ORDER BY rank_index, attr
                """
            ),
            {"id": operator_id},
        ).mappings().all()
        pot_by_rank: dict[int, dict[str, float]] = {}
        for r in pot_rows:
            ri = int(r["rank_index"])
            pot_by_rank.setdefault(ri, {"hp": 0.0, "atk": 0.0, "def": 0.0, "aspd": 0.0, "res": 0.0})
            attr = str(r["attr"] or "")
            if attr in pot_by_rank[ri]:
                pot_by_rank[ri][attr] += float(r["value"] or 0)
        max_ri = max(pot_by_rank.keys(), default=-1)
        potential_ranks = [
            pot_by_rank.get(i, {"hp": 0.0, "atk": 0.0, "def": 0.0, "aspd": 0.0, "res": 0.0})
            for i in range(max_ri + 1)
        ]

        pos = (op.get("position") or "").upper() or None
        sub_id = op.get("sub_profession")
        sub_cn = None
        try:
            from app.data.store import get_store

            store = get_store()
            sub_cn = (
                (store.uni_equip_table.get("subProfDict") or {})
                .get(sub_id or "", {})
                .get("subProfessionName")
            )
            if not pos:
                raw = store.character_table.get(operator_id) or {}
                pos = (raw.get("position") or "").upper() or None
        except Exception:
            pass

        return {
            "id": op["id"],
            "name": op["name"],
            "rarity": int(op["rarity"] or 0),
            "profession": op["profession"],
            "profession_cn": op["profession_cn"],
            "sub_profession": sub_id,
            "sub_profession_cn": sub_cn,
            "position": pos,
            "position_cn": {"MELEE": "近战", "RANGED": "远程"}.get(pos or "", pos),
            "description": op["description"],
            "phases": phases,
            "skills": [],
            "talents": talents_out,
            "modules": modules,
            "favor_key_frames": favor_key_frames,
            "potential_ranks": potential_ranks,
            "raw_phases": raw_phases,
        }


def get_operator_skills(operator_id: str) -> list[dict]:
    """从 MySQL 返回前端自动填充所需的 Lv7 与最高技能等级。"""
    init_schema()
    with get_engine().connect() as conn:
        skills = conn.execute(
            text(
                """
                SELECT skill_id,skill_index,max_level
                FROM operator_skills
                WHERE operator_id=:operator_id
                ORDER BY skill_index
                """
            ),
            {"operator_id": operator_id},
        ).mappings().all()
        result: list[dict] = []
        for skill in skills:
            max_level = int(skill["max_level"] or 0)
            target_levels = [7] if max_level <= 7 else [7, max_level]
            rows = conn.execute(
                text(
                    """
                    SELECT level,name,description,duration,sp_cost,sp_init,parsed_effects
                    FROM operator_skill_levels
                    WHERE operator_id=:operator_id AND skill_id=:skill_id
                    ORDER BY level
                    """
                ),
                {
                    "operator_id": operator_id,
                    "skill_id": skill["skill_id"],
                },
            ).mappings().all()
            rows = [row for row in rows if int(row["level"]) in target_levels]
            levels_out = []
            for row in rows:
                parsed = row["parsed_effects"]
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
                parsed = parsed or {}
                levels_out.append(
                    {
                        "level": int(row["level"]),
                        "name": row["name"],
                        "description": row["description"],
                        "duration": float(row["duration"] or 0),
                        "sp_cost": row["sp_cost"],
                        "sp_init": row["sp_init"],
                        **parsed,
                    }
                )
            if levels_out:
                result.append(
                    {
                        "skill_id": skill["skill_id"],
                        "skill_name": levels_out[0].get("name"),
                        "max_level": max_level,
                        "levels": levels_out,
                    }
                )
        return result


def search_enemies(
    q: str | None = None,
    limit: int = 50,
    theme_id: str | None = None,
) -> list[dict]:
    init_schema()
    params: dict[str, Any] = {"limit": limit}
    if theme_id:
        sql = """
            SELECT e.id, e.name, e.enemy_level, e.description
            FROM theme_enemies te
            JOIN enemies e ON e.id = te.enemy_id
            WHERE te.theme_id = :theme_id
        """
        params["theme_id"] = theme_id
        if q and q.strip():
            sql += " AND (e.name LIKE :like OR e.id LIKE :like)"
            params["like"] = f"%{q.strip()}%"
        sql += " ORDER BY e.name ASC LIMIT :limit"
    else:
        sql = "SELECT id,name,enemy_level,description FROM enemies"
        if q and q.strip():
            sql += " WHERE name LIKE :like OR id LIKE :like"
            params["like"] = f"%{q.strip()}%"
        sql += " ORDER BY name ASC LIMIT :limit"
    with get_engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]


def _enemy_diff_targets(enemy_level: str | None) -> set[str]:
    """难度修正目标：普通敌 + 对应精英/领袖。"""
    targets = {"enemy"}
    lv = (enemy_level or "").upper()
    if lv == "ELITE":
        targets.add("elite_enemy")
    elif lv == "BOSS":
        targets.add("boss")
    return targets


def get_enemy_row(enemy_id: str, level: int = 0, theme_id: str | None = None, equivalent_grade: int = 0) -> dict | None:
    init_schema()
    with get_engine().connect() as conn:
        en = conn.execute(text("SELECT * FROM enemies WHERE id=:id"), {"id": enemy_id}).mappings().first()
        if not en:
            return None
        lv = conn.execute(
            text(
                """
                SELECT * FROM enemy_levels
                WHERE enemy_id=:id AND level_index=:li
                """
            ),
            {"id": enemy_id, "li": level},
        ).mappings().first()
        if not lv:
            lv = conn.execute(
                text("SELECT * FROM enemy_levels WHERE enemy_id=:id ORDER BY level_index LIMIT 1"),
                {"id": enemy_id},
            ).mappings().first()
        max_lv = conn.execute(
            text("SELECT COUNT(*) FROM enemy_levels WHERE enemy_id=:id"),
            {"id": enemy_id},
        ).scalar() or 0

        attrs = {
            "hp": float((lv or {}).get("hp") or 0),
            "atk": float((lv or {}).get("atk") or 0),
            "def": float((lv or {}).get("def_stat") or 0),
            "magic_resistance": float((lv or {}).get("magic_resistance") or 0),
            "move_speed": float((lv or {}).get("move_speed") or 0),
            "attack_speed": float((lv or {}).get("attack_speed") or 0),
            "range_radius": float((lv or {}).get("range_radius") or 0),
            "damage_type": en["damage_type"],
        }
        applied_mods: list[dict] = []
        damage_taken = {"phys": 0.0, "arts": 0.0}
        if theme_id:
            mods = conn.execute(
                text(
                    """
                    SELECT target,attr,value,op,note FROM difficulty_stat_mods
                    WHERE theme_id=:tid AND equivalent_grade<=:eq
                    ORDER BY equivalent_grade
                    """
                ),
                {"tid": theme_id, "eq": equivalent_grade},
            ).mappings().all()
            targets = _enemy_diff_targets(en.get("enemy_level"))
            mul = {"hp": 0.0, "atk": 0.0, "def": 0.0}
            for m in mods:
                if m["target"] not in targets:
                    continue
                applied_mods.append(dict(m))
                attr = m["attr"]
                val = float(m["value"] or 0)
                if attr == "hp_pct":
                    mul["hp"] += val
                elif attr == "atk_pct":
                    mul["atk"] += val
                elif attr == "def_pct":
                    mul["def"] += val
                elif attr == "damage_taken_phys_pct":
                    damage_taken["phys"] += val
                elif attr == "damage_taken_arts_pct":
                    damage_taken["arts"] += val
            attrs["hp"] *= 1.0 + mul["hp"]
            attrs["atk"] *= 1.0 + mul["atk"]
            attrs["def"] *= 1.0 + mul["def"]

        return {
            "id": en["id"],
            "name": en["name"],
            "description": en["description"],
            "enemy_level": en["enemy_level"],
            "level_index": level,
            "attributes": attrs,
            "raw_level_count": int(max_lv),
            "difficulty_mods": applied_mods,
            "damage_taken": damage_taken,
        }


def refresh_theme_enemies(store: Any, *, download_missing: bool = True) -> dict[str, int]:
    """仅刷新主题敌人池（不重建其它表）。"""
    init_schema()
    from app.data.theme_enemy_sync import extract_theme_enemy_ids, iter_theme_details

    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE TABLE theme_enemies"))
        te_count = 0
        per_theme: dict[str, int] = {}
        for tid, detail in iter_theme_details(store.roguelike_topic_table):
            ids = extract_theme_enemy_ids(
                tid, detail, download_missing=download_missing, max_workers=8
            )
            n = 0
            for eid in ids:
                exists = conn.execute(
                    text("SELECT 1 FROM enemies WHERE id=:id"), {"id": eid}
                ).first()
                if not exists:
                    continue
                conn.execute(
                    text("INSERT IGNORE INTO theme_enemies(theme_id,enemy_id) VALUES(:tid,:eid)"),
                    {"tid": tid, "eid": eid},
                )
                n += 1
                te_count += 1
            per_theme[tid] = n
            logger.info(f"theme_enemies {tid}: {n}")
    set_meta("theme_enemies_refreshed_at", datetime.now(timezone.utc).isoformat())
    set_meta("theme_enemies_counts", per_theme)
    return {"theme_enemies": te_count, **{f"theme:{k}": v for k, v in per_theme.items()}}


def search_relics(
    theme: str | None = None,
    q: str | None = None,
    limit: int = 500,
    equivalent_grade: int | None = None,
) -> list[dict]:
    init_schema()
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if theme:
        clauses.append("r.theme_id = :theme")
        params["theme"] = theme
    if q and q.strip():
        clauses.append("(r.name LIKE :like OR r.id LIKE :like OR r.usage_text LIKE :like)")
        params["like"] = f"%{q.strip()}%"
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT r.id, r.theme_id AS theme, t.name AS theme_name, r.name,
               r.usage_text AS `usage`, r.description, r.icon_id, r.order_id
        FROM relics r
        LEFT JOIN themes t ON t.id = r.theme_id
        {where}
        ORDER BY r.order_id ASC, r.name ASC
        LIMIT :limit
    """
    with get_engine().connect() as conn:
        items = [dict(r) for r in conn.execute(text(sql), params).mappings().all()]
        # 列表默认只展示升级链「根」藏品，变体通过 equivalent_grade 解析展示
        upgrade_variants = {
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT relic_id FROM relic_upgrade_steps
                    WHERE equivalent_grade_min > 0
                    """
                )
            ).fetchall()
        }
        items = [d for d in items if d["id"] not in upgrade_variants]
        for d in items:
            d["icon_url"] = f"/api/v1/assets/relic/{d['id']}"
            if equivalent_grade is not None:
                resolved = resolve_relic_for_grade(d["id"], int(equivalent_grade), conn=conn)
                if resolved and resolved["id"] != d["id"]:
                    d["resolved_id"] = resolved["id"]
                    d["resolved_name"] = resolved.get("name")
                    d["name"] = resolved.get("name") or d["name"]
                    d["usage"] = resolved.get("usage") or d["usage"]
                    d["icon_id"] = resolved.get("icon_id") or d["icon_id"]
                    # 变体图常与根藏品共用；URL 仍指向变体，服务端会回退根图
                    d["icon_url"] = f"/api/v1/assets/relic/{resolved['id']}"
                    d["icon_fallback_id"] = d["id"]
            # attach compact effects（变体无效果时回退根藏品）
            rid = d.get("resolved_id") or d["id"]
            eff = conn.execute(
                text("SELECT attr,value,target FROM relic_effect_rules WHERE relic_id=:id AND calculation_status='active' AND attr<>'ignored'"),
                {"id": rid},
            ).mappings().all()
            if not eff and d.get("resolved_id"):
                eff = conn.execute(
                    text("SELECT attr,value,target FROM relic_effect_rules WHERE relic_id=:id AND calculation_status='active' AND attr<>'ignored'"),
                    {"id": d["id"]},
                ).mappings().all()
            d["effects"] = [dict(e) for e in eff]
        return items


def list_themes_db() -> list[dict]:
    init_schema()
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT t.id, t.name, COUNT(r.id) AS relic_count
                FROM themes t
                LEFT JOIN relics r
                  ON r.theme_id = t.id
                 AND r.id NOT IN (
                   SELECT relic_id FROM relic_upgrade_steps WHERE equivalent_grade_min > 0
                 )
                GROUP BY t.id, t.name
                ORDER BY t.id
                """
            )
        ).mappings().all()
        return [dict(r) for r in rows]


def list_theme_difficulties(theme_id: str) -> list[dict]:
    init_schema()
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, theme_id, mode_difficulty, grade, equivalent_grade, name,
                       score_factor, rule_desc, color, sort_id
                FROM theme_difficulties
                WHERE theme_id=:tid
                ORDER BY
                  CASE mode_difficulty
                    WHEN 'NORMAL' THEN 0
                    WHEN 'EASY' THEN 1
                    WHEN 'MONTH_TEAM' THEN 2
                    WHEN 'CHALLENGE' THEN 3
                    ELSE 9
                  END,
                  grade ASC,
                  equivalent_grade ASC,
                  sort_id IS NULL, sort_id
                """
            ),
            {"tid": theme_id},
        ).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["key"] = f"{d['mode_difficulty']}:{int(d['grade'])}"
            out.append(d)
        return out


def get_relic_row(relic_id: str) -> dict | None:
    init_schema()
    with get_engine().connect() as conn:
        r = conn.execute(
            text(
                """
                SELECT r.*, t.name AS theme_name
                FROM relics r LEFT JOIN themes t ON t.id=r.theme_id
                WHERE r.id=:id
                """
            ),
            {"id": relic_id},
        ).mappings().first()
        if not r:
            return None
        d = dict(r)
        d["theme"] = d.pop("theme_id")
        d["usage"] = d.pop("usage_text")
        d["effects"] = [
            dict(e)
            for e in conn.execute(
                text("""
                  SELECT attr,value,target,source,note,operation,value_expr,when_param,
                         calculation_status,rule_version,review_status
                  FROM relic_effect_rules
                  WHERE relic_id=:id AND calculation_status='active' AND attr<>'ignored'
                  ORDER BY display_order,id
                """),
                {"id": relic_id},
            ).mappings().all()
        ]
        statuses = conn.execute(text("""
          SELECT calculation_status,ignored_reason FROM relic_effect_rules
          WHERE relic_id=:id ORDER BY calculation_status='active' DESC,id
        """), {"id": relic_id}).mappings().all()
        d["calculation_status"] = "active" if any(x["calculation_status"] == "active" for x in statuses) else "ignored"
        d["ignored_reason"] = next((x["ignored_reason"] for x in statuses if x["calculation_status"] == "ignored" and x["ignored_reason"]), None)
        d["icon_url"] = f"/api/v1/assets/relic/{relic_id}"
        return d


def resolve_relic_for_grade(relic_id: str, equivalent_grade: int, conn=None) -> dict | None:
    """按升级链把 relic_id 解析到当前难度生效的变体。"""
    own = conn is None
    if own:
        conn = get_engine().connect()
    try:
        # 找到包含该 relic 的组，取 <= grade 最高一步
        step = conn.execute(
            text(
                """
                SELECT s2.relic_id
                FROM relic_upgrade_steps s1
                JOIN relic_upgrade_steps s2 ON s2.group_id = s1.group_id
                WHERE s1.relic_id = :rid AND s2.equivalent_grade_min <= :eq
                ORDER BY s2.equivalent_grade_min DESC
                LIMIT 1
                """
            ),
            {"rid": relic_id, "eq": equivalent_grade},
        ).first()
        target_id = step[0] if step else relic_id
        row = conn.execute(
            text(
                """
                SELECT id, name, usage_text AS `usage`, description, icon_id, theme_id AS theme, order_id
                FROM relics WHERE id=:id
                """
            ),
            {"id": target_id},
        ).mappings().first()
        return dict(row) if row else None
    finally:
        if own:
            conn.close()


def get_relic_rule_rows(relic_ids: list[str], equivalent_grade: int = 0) -> list[dict]:
    """Return active/manual MySQL relic rules for resolved relic ids."""
    init_schema()
    rows: list[dict] = []
    with get_engine().connect() as conn:
        for rid in relic_ids or []:
            resolved = resolve_relic_for_grade(rid, equivalent_grade) or {"id": rid}
            actual = resolved.get("id") or rid
            found = conn.execute(text("""
                SELECT r.*,x.name AS relic_name
                FROM relic_effect_rules r JOIN relics x ON x.id=r.relic_id
                WHERE r.relic_id=:rid
                ORDER BY r.display_order,r.id
            """), {"rid": actual}).mappings().all()
            rows.extend(dict(row) for row in found)
    return rows


def get_relic_condition_schemas(theme_id: str | None = None) -> dict[str, dict]:
    init_schema()
    where = "WHERE x.theme_id=:theme" if theme_id else ""
    params = {"theme": theme_id} if theme_id else {}
    with get_engine().connect() as conn:
        param_rows = conn.execute(text(f"""
            SELECT p.*,x.name AS relic_name FROM relic_condition_params p
            JOIN relics x ON x.id=p.relic_id {where}
            ORDER BY p.relic_id,p.display_order,p.param_id
        """), params).mappings().all()
        rule_rows = conn.execute(text(f"""
            SELECT r.* FROM relic_effect_rules r
            JOIN relics x ON x.id=r.relic_id
            {where}
            ORDER BY r.relic_id,r.display_order,r.id
        """), params).mappings().all()
    out: dict[str, dict] = {}
    for row in param_rows:
        auto = row["auto_rule"]
        if isinstance(auto, str):
            auto = json.loads(auto)
        item = {
            "id": row["param_id"], "type": row["param_type"], "label": row["label"],
            "default": bool(row["default_value"]) if row["param_type"] == "toggle" else float(row["default_value"]),
        }
        if row["min_value"] is not None: item["min"] = float(row["min_value"])
        if row["max_value"] is not None: item["max"] = float(row["max_value"])
        if row["step_value"] is not None: item["step"] = float(row["step_value"])
        if row["unit"]: item["unit"] = row["unit"]
        if auto: item["auto"] = auto
        out.setdefault(row["relic_id"], {"name": row["relic_name"], "params": [], "operator_effects": [], "replace_operator_panel": True})["params"].append(item)
    for row in rule_rows:
        if row["relic_id"] not in out or row["calculation_status"] == "ignored" or row["target"] != "operator":
            continue
        effect = {"attr": row["attr"], "value": float(row["value"])}
        if row["value_expr"]: effect["expr"] = row["value_expr"]
        if row["when_param"]: effect["when"] = row["when_param"]
        effect["operation"] = row["operation"]
        out.setdefault(row["relic_id"], {"name": row["relic_id"], "params": [], "operator_effects": [], "replace_operator_panel": True})["operator_effects"].append(effect)
    return {key: value for key, value in out.items() if value["params"] or value["operator_effects"]}


def get_theme_outer_buffs() -> dict[str, dict]:
    init_schema()
    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT * FROM theme_outer_buffs")).mappings().all()
    return {row["theme_id"]: {key: row[key] for key in ("name", "atk_pct", "hp_pct", "def_pct", "aspd", "note")} for row in rows}


def get_relic_effects_merged(relic_ids: list[str], equivalent_grade: int = 0) -> list[dict]:
    """解析升级链后返回 effect 行列表；变体无效果时回退到同链更低档。"""
    init_schema()
    with get_engine().connect() as conn:
        effects: list[dict] = []
        seen_ids: set[str] = set()
        for rid in relic_ids:
            resolved = resolve_relic_for_grade(rid, equivalent_grade, conn=conn)
            target_id = (resolved or {}).get("id") or rid
            # 收集同组内 <= grade 的全部候选（高→低），取第一份非空规则
            candidates: list[str] = [target_id]
            steps = conn.execute(
                text(
                    """
                    SELECT s2.relic_id, s2.equivalent_grade_min
                    FROM relic_upgrade_steps s1
                    JOIN relic_upgrade_steps s2 ON s2.group_id = s1.group_id
                    WHERE s1.relic_id = :rid AND s2.equivalent_grade_min <= :eq
                    ORDER BY s2.equivalent_grade_min DESC
                    """
                ),
                {"rid": rid, "eq": equivalent_grade},
            ).fetchall()
            if steps:
                candidates = [row[0] for row in steps]
            chosen_rows = []
            for cid in candidates:
                rows = conn.execute(
                    text("""
                        SELECT relic_id,target,attr,value,source,note,operation,rule_version,review_status
                        FROM relic_effect_rules
                        WHERE relic_id=:id AND calculation_status='active'
                          AND when_param IS NULL AND value_expr IS NULL AND attr<>'ignored'
                          AND NOT EXISTS (SELECT 1 FROM relic_condition_params p WHERE p.relic_id=relic_effect_rules.relic_id)
                    """),
                    {"id": cid},
                ).mappings().all()
                if rows:
                    chosen_rows = [dict(x) for x in rows]
                    break
            if not chosen_rows:
                rows = conn.execute(
                    text("""
                        SELECT relic_id,target,attr,value,source,note,operation,rule_version,review_status
                        FROM relic_effect_rules
                        WHERE relic_id=:id AND calculation_status='active'
                          AND when_param IS NULL AND value_expr IS NULL AND attr<>'ignored'
                          AND NOT EXISTS (SELECT 1 FROM relic_condition_params p WHERE p.relic_id=relic_effect_rules.relic_id)
                    """),
                    {"id": rid},
                ).mappings().all()
                chosen_rows = [dict(x) for x in rows]
            for row in chosen_rows:
                key = f"{row['relic_id']}:{row['target']}:{row['attr']}:{row['value']}"
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                effects.append(row)
        return effects


def get_module(module_id: str) -> dict | None:
    init_schema()
    with get_engine().connect() as conn:
        m = conn.execute(text("SELECT * FROM modules WHERE id=:id"), {"id": module_id}).mappings().first()
        if not m:
            return None
        levels = conn.execute(
            text("SELECT level,atk,atk_pct,hp,defense,attack_speed,trait_effects,talent_effects FROM module_levels WHERE module_id=:id ORDER BY level"),
            {"id": module_id},
        ).mappings().all()
        return {
            "id": m["id"],
            "name": m["name"],
            "type": m["type_name"],
            "description": m["description"],
            "max_level": int(m["max_level"] or 1),
            "levels": [_module_level_dict(lv) for lv in levels],
        }


def _module_level_dict(row: Any) -> dict:
    result = dict(row)
    for field in ("trait_effects", "talent_effects"):
        value = result.get(field)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                value = []
        result[field] = value or []
    return result


# 兼容旧名
def db_path() -> Path:
    return Path(f"mysql://{db_dsn_display()}")
