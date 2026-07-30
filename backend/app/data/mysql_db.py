"""MySQL 主库：连接、建表、导入、查询。"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import REPO_ROOT, settings

_lock = threading.RLock()
_engine: Engine | None = None

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
        "operator_talents",
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


def _parse_rule_desc_mods(theme_id: str, grade: int, rule_desc: str) -> list[dict]:
    """从难度 ruleDesc 启发式抽取敌人数值修正。"""
    text = rule_desc or ""
    mods: list[dict] = []
    if not text:
        return mods

    # 敌人受到的物理与法术伤害降低 x%
    m = re.search(r"受到的?(?:物理与法术|物理和法术)?伤害降低\s*(\d+(?:\.\d+)?)\s*%", text)
    if m:
        v = -float(m.group(1)) / 100.0
        mods.append({"theme_id": theme_id, "equivalent_grade": grade, "target": "enemy",
                     "attr": "damage_taken_phys_pct", "value": v, "op": "mul", "note": "ruleDesc"})
        mods.append({"theme_id": theme_id, "equivalent_grade": grade, "target": "enemy",
                     "attr": "damage_taken_arts_pct", "value": v, "op": "mul", "note": "ruleDesc"})

    m = re.search(r"(?:精英|领袖|boss|Boss).{0,12}受到的?(?:物理与法术|物理和法术)?伤害降低\s*(\d+(?:\.\d+)?)\s*%", text)
    if m:
        v = -float(m.group(1)) / 100.0
        mods.append({"theme_id": theme_id, "equivalent_grade": grade, "target": "elite_enemy",
                     "attr": "damage_taken_phys_pct", "value": v, "op": "mul", "note": "ruleDesc elite"})
        mods.append({"theme_id": theme_id, "equivalent_grade": grade, "target": "boss",
                     "attr": "damage_taken_phys_pct", "value": v, "op": "mul", "note": "ruleDesc boss"})

    for attr_cn, attr in (("攻击力", "atk_pct"), ("生命", "hp_pct"), ("防御力", "def_pct"), ("防御", "def_pct")):
        m = re.search(rf"敌人.{{0,6}}{attr_cn}.{{0,6}}(?:提升|增加|\+)\s*(\d+(?:\.\d+)?)\s*%", text)
        if m:
            mods.append({"theme_id": theme_id, "equivalent_grade": grade, "target": "enemy",
                         "attr": attr, "value": float(m.group(1)) / 100.0, "op": "mul", "note": "ruleDesc"})
    return mods


def rebuild_from_store(store: Any) -> dict[str, int]:
    """从 GameDataStore 全量重建 MySQL。"""
    with _lock:
        init_schema()
        eng = get_engine()
        with eng.begin() as conn:
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
                                INSERT INTO module_levels(module_id,level,atk,atk_pct,hp,defense,attack_speed)
                                VALUES(:mid,:level,:atk,:atk_pct,:hp,:defense,:attack_speed)
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
                            },
                        )
                # talents
                for ti, talent in enumerate(raw.get("talents") or []):
                    for ci, cand in enumerate(talent.get("candidates") or []):
                        bb = cand.get("blackboard") or []
                        if isinstance(bb, list) and bb:
                            # 确保可序列化
                            try:
                                bb_json = json.dumps(bb, ensure_ascii=False)
                            except Exception:
                                bb_json = None
                        else:
                            bb_json = None
                        conn.execute(
                            text(
                                """
                                INSERT IGNORE INTO operator_talents(operator_id,talent_index,name,description,potential_rank,blackboard)
                                VALUES(:oid,:ti,:name,:desc,:pr,:bb)
                                """
                            ),
                            {
                                "oid": brief["id"],
                                "ti": ti,
                                "name": cand.get("name") or "",
                                "desc": cand.get("description") or "",
                                "pr": int(cand.get("requiredPotentialRank") or 0),
                                "bb": bb_json,
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

            counts = {
                "operators": op_count,
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
                    SELECT level,atk,atk_pct,hp,defense,attack_speed
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
                    "levels": [dict(lv) for lv in levels],
                }
            )

        # talents
        talents_rows = conn.execute(
            text(
                """
                SELECT talent_index,name,description,potential_rank,blackboard
                FROM operator_talents WHERE operator_id=:id
                ORDER BY talent_index, potential_rank
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
                "name": t["name"],
                "description": t["description"],
                "potential_rank": int(t["potential_rank"] or 0),
                "blackboard": bb,
            })

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
            "potential_ranks": [],
            "raw_phases": raw_phases,
        }


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
                # 面板数值：仅叠 hp/atk/def 百分比
                if m["target"] != "enemy":
                    # elite/boss 专属伤害减免等不改面板数值
                    continue
                attr = m["attr"]
                val = float(m["value"] or 0)
                if attr == "hp_pct":
                    mul["hp"] += val
                elif attr == "atk_pct":
                    mul["atk"] += val
                elif attr == "def_pct":
                    mul["def"] += val
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
                text("SELECT attr,value,target FROM relic_effects WHERE relic_id=:id"),
                {"id": rid},
            ).mappings().all()
            if not eff and d.get("resolved_id"):
                eff = conn.execute(
                    text("SELECT attr,value,target FROM relic_effects WHERE relic_id=:id"),
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
                text("SELECT attr,value,target,source,note FROM relic_effects WHERE relic_id=:id"),
                {"id": relic_id},
            ).mappings().all()
        ]
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


def get_relic_effects_merged(relic_ids: list[str], equivalent_grade: int = 0) -> list[dict]:
    """解析升级链后返回 effect 行列表；变体无效果时回退到同链更低档。"""
    init_schema()
    with get_engine().connect() as conn:
        effects: list[dict] = []
        seen_ids: set[str] = set()
        for rid in relic_ids:
            resolved = resolve_relic_for_grade(rid, equivalent_grade, conn=conn)
            target_id = (resolved or {}).get("id") or rid
            # 收集同组内 <= grade 的全部候选（高→低），取第一份非空 effects
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
                    text(
                        "SELECT relic_id,target,attr,value,source,note FROM relic_effects WHERE relic_id=:id"
                    ),
                    {"id": cid},
                ).mappings().all()
                if rows:
                    chosen_rows = [dict(x) for x in rows]
                    break
            if not chosen_rows:
                # 无升级链时再直接查一次原 id
                rows = conn.execute(
                    text(
                        "SELECT relic_id,target,attr,value,source,note FROM relic_effects WHERE relic_id=:id"
                    ),
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
            text("SELECT level,atk,atk_pct,hp,defense,attack_speed FROM module_levels WHERE module_id=:id ORDER BY level"),
            {"id": module_id},
        ).mappings().all()
        return {
            "id": m["id"],
            "name": m["name"],
            "type": m["type_name"],
            "description": m["description"],
            "max_level": int(m["max_level"] or 1),
            "levels": [dict(lv) for lv in levels],
        }


# 兼容旧名
def db_path() -> Path:
    return Path(f"mysql://{db_dsn_display()}")
