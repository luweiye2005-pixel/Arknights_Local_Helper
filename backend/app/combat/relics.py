"""藏品计算兼容门面。

实现已按数据模型、条件求值、文本解析与运行时规则拆分。
"""
from app.combat.relic_models import CombatModifiers, EnemyStatModifiers
from app.combat.relic_conditions import (
    safe_eval_expr,
    load_relic_conditions,
    load_outer_buffs,
    list_condition_schemas,
    get_outer_buff,
    match_applies_auto,
    build_conditional_relic_modifiers,
    build_relic_contributions,
    outer_buff_to_modifiers,
    manual_bonus_to_modifiers,
)

from app.combat.relic_parsing import (
    parse_enemy_relic_text,
    enemy_modifiers_from_effect_rows,
    build_enemy_relic_modifiers,
    load_relic_patches,
    parse_relic_text,
    modifiers_from_patch,
    modifiers_from_effect_rows,
    normalize_damage_amps,
)

from app.combat.relic_runtime import (
    build_relic_modifiers,
)

