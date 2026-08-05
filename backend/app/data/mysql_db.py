"""MySQL 数据访问兼容门面。

实现按连接/建表、数据导入和查询拆分；保留原有导入路径。
"""
from app.data.mysql_core import (
    source_name,
    get_engine,
    init_schema,
    ensure_module_effect_schema,
    ensure_talent_and_potential_schema,
    ensure_operator_position_column,
    set_meta,
    get_meta,
    db_counts,
    db_dsn_display,
    db_path,
)

from app.data.mysql_rebuild import (
    rebuild_from_store,
    refresh_modules_from_store,
)

from app.data.mysql_queries import (
    search_operators,
    get_operator_detail,
    get_operator_skills,
    search_enemies,
    get_enemy_row,
    refresh_theme_enemies,
    search_relics,
    list_themes_db,
    list_theme_difficulties,
    get_relic_row,
    resolve_relic_for_grade,
    get_relic_rule_rows,
    get_relic_condition_schemas,
    get_theme_outer_buffs,
    get_relic_effects_merged,
    get_module,
)

from app.data.mysql_rebuild import _parse_rule_desc_mods, _skill_level_row
