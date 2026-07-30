"""可选：连真实 MySQL 的一致性检查（无库则跳过）。"""
import pytest

from app.data import db as gdb


def _mysql_ready() -> bool:
    try:
        c = gdb.db_counts()
        return c.get("relics", 0) > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _mysql_ready(), reason="MySQL 未就绪或未灌库")


def test_theme_relic_count_matches_list():
    for t in gdb.list_themes_db():
        items = gdb.search_relics(theme=t["id"], limit=5000)
        assert t["relic_count"] == len(items), f"{t['id']}: count={t['relic_count']} list={len(items)}"


def test_difficulty_keys_unique_per_theme():
    for t in gdb.list_themes_db():
        diffs = gdb.list_theme_difficulties(t["id"])
        keys = [d["key"] for d in diffs]
        assert len(keys) == len(set(keys)), f"duplicate keys in {t['id']}: {keys}"


def test_resolve_upgrade_variant():
    # 任取一条升级链
    from sqlalchemy import text
    from app.data.mysql_db import get_engine, resolve_relic_for_grade

    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT s0.relic_id AS base_id, s1.relic_id AS high_id, s1.equivalent_grade_min AS grade
                FROM relic_upgrade_steps s0
                JOIN relic_upgrade_steps s1 ON s1.group_id = s0.group_id
                WHERE s0.equivalent_grade_min = 0 AND s1.equivalent_grade_min > 0
                LIMIT 1
                """
            )
        ).mappings().first()
    if not row:
        pytest.skip("无升级链数据")
    resolved = resolve_relic_for_grade(row["base_id"], int(row["grade"]))
    assert resolved is not None
    assert resolved["id"] == row["high_id"]


def test_operator_detail_has_phases():
    ops = gdb.search_operators(limit=1)
    assert ops
    detail = gdb.get_operator_detail(ops[0]["id"])
    assert detail is not None
    assert detail["phases"]
    assert detail["raw_phases"]
