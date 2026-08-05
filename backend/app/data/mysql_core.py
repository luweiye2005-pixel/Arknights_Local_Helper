"""MySQL 连接、建表与元数据操作。"""
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




# 兼容数据后端统一接口。
def db_path() -> Path:
    return Path(f"mysql://{db_dsn_display()}")

