"""Apply the curated relic calculation fixes documented in docs/relic-calculation-fix-plan.md.

The migration is idempotent. It intentionally models only operator/enemy panel
stats and final single-hit damage. Unsupported event, DP, SP, control, block,
and recruitment effects are either omitted or marked ignored.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.mysql_db import get_engine, init_schema  # noqa: E402

VERSION = 5


def reset(conn, relic_id: str) -> None:
    conn.execute(text("DELETE FROM relic_condition_params WHERE relic_id=:id"), {"id": relic_id})
    conn.execute(text("DELETE FROM relic_effect_rules WHERE relic_id=:id"), {"id": relic_id})


def param(
    conn,
    relic_id: str,
    param_id: str,
    label: str,
    *,
    param_type: str = "toggle",
    default: float = 0,
    minimum: float | None = 0,
    maximum: float | None = 1,
    step: float | None = 1,
    unit: str | None = None,
    auto: dict | None = None,
    order: int = 0,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO relic_condition_params(
              relic_id,param_id,param_type,label,default_value,min_value,max_value,
              step_value,unit,auto_rule,display_order,rule_version,review_status
            ) VALUES(:rid,:pid,:ptype,:label,:default,:min,:max,:step,:unit,CAST(:auto AS JSON),:ord,:version,'approved')
            """
        ),
        {
            "rid": relic_id,
            "pid": param_id,
            "ptype": param_type,
            "label": label,
            "default": default,
            "min": minimum,
            "max": maximum,
            "step": step,
            "unit": unit,
            "auto": json.dumps(auto, ensure_ascii=False) if auto else "null",
            "ord": order,
            "version": VERSION,
        },
    )


def rule(
    conn,
    relic_id: str,
    target: str,
    attr: str,
    value: float = 0,
    *,
    expr: str | None = None,
    when: str | None = None,
    order: int = 0,
    note: str = "relic fix plan v2",
) -> None:
    operation = "multiply" if attr in {"damage_pct", "phys_damage_pct", "arts_damage_pct", "true_damage_pct", "elemental_damage_pct"} else "add"
    conn.execute(
        text(
            """
            INSERT INTO relic_effect_rules(
              relic_id,target,attr,operation,value,value_expr,when_param,damage_type,
              calculation_status,ignored_reason,source,rule_version,review_status,
              display_order,note,reviewed_at
            ) VALUES(:rid,:target,:attr,:operation,:value,:expr,:when,NULL,
              'active',NULL,'manual',:version,'approved',:ord,:note,NOW())
            """
        ),
        {
            "rid": relic_id,
            "target": target,
            "attr": attr,
            "operation": operation,
            "value": value,
            "expr": expr,
            "when": when,
            "version": VERSION,
            "ord": order,
            "note": note,
        },
    )


def ignored(conn, relic_id: str, reason: str) -> None:
    reset(conn, relic_id)
    conn.execute(
        text(
            """
            INSERT INTO relic_effect_rules(
              relic_id,target,attr,operation,value,calculation_status,ignored_reason,
              source,rule_version,review_status,display_order,note,reviewed_at
            ) VALUES(:rid,'meta','ignored','add',0,'ignored',:reason,
              'manual',:version,'approved',9999,'relic fix plan v2',NOW())
            """
        ),
        {"rid": relic_id, "reason": reason, "version": VERSION},
    )


def auto_toggle(conn, relic_id: str, auto: dict, *, param_id: str = "applies", label: str = "当前干员满足适用条件", order: int = 0) -> None:
    param(conn, relic_id, param_id, label, auto=auto, order=order)


def profession_fix(conn, relic_id: str, professions: list[str], effects: list[tuple[str, float]]) -> None:
    reset(conn, relic_id)
    auto_toggle(conn, relic_id, {"profession": professions})
    for index, (attr, value) in enumerate(effects):
        rule(conn, relic_id, "operator", attr, value, when="applies", order=index)


def subprofession_fix(conn, relic_id: str, names: list[str], effects: list[tuple[str, float]], *, condition: tuple[str, str] | None = None) -> None:
    reset(conn, relic_id)
    auto_toggle(conn, relic_id, {"sub_profession_cn_any": names})
    if condition:
        pid, label = condition
        param(conn, relic_id, pid, label, order=1)
    for index, (attr, value) in enumerate(effects):
        expr = f"{value}*applies*{condition[0]}" if condition else None
        rule(conn, relic_id, "operator", attr, 0 if expr else value, expr=expr, when=None if expr else "applies", order=index)


def apply_standard_profession_rules(conn) -> None:
    groups = [
        (["先锋", "PIONEER"], 0.60, [
            "rogue_1_relic_p01", "rogue_2_relic_fight_47", "rogue_3_relic_legacy_102",
            "rogue_4_relic_legacy_97", "rogue_5_relic_legacy_98",
        ]),
        (["近卫", "WARRIOR"], 0.40, [
            "rogue_1_relic_p06", "rogue_2_relic_fight_51", "rogue_3_relic_legacy_106",
            "rogue_4_relic_legacy_101", "rogue_5_relic_legacy_100",
        ]),
        (["重装", "TANK"], 0.40, [
            "rogue_1_relic_p11", "rogue_2_relic_fight_56", "rogue_3_relic_legacy_110",
            "rogue_4_relic_legacy_105", "rogue_5_relic_legacy_99",
        ]),
        (["狙击", "SNIPER"], 0.60, [
            "rogue_1_relic_p16", "rogue_2_relic_fight_60", "rogue_3_relic_legacy_113",
            "rogue_4_relic_legacy_109", "rogue_5_relic_legacy_102", "rogue_6_relic_legacy_70",
        ]),
        (["术师", "CASTER"], 0.60, [
            "rogue_1_relic_p21", "rogue_2_relic_fight_64", "rogue_3_relic_legacy_117",
            "rogue_4_relic_legacy_113", "rogue_5_relic_legacy_103", "rogue_6_relic_legacy_72",
        ]),
        (["辅助", "SUPPORT"], 0.60, [
            "rogue_1_relic_p26", "rogue_2_relic_fight_68", "rogue_3_relic_legacy_121",
            "rogue_4_relic_legacy_117", "rogue_6_relic_legacy_78",
        ]),
        (["医疗", "MEDIC"], 0.60, [
            "rogue_1_relic_p31", "rogue_2_relic_fight_72", "rogue_3_relic_legacy_125",
            "rogue_4_relic_legacy_121", "rogue_5_relic_legacy_106",
        ]),
        (["特种", "SPECIAL"], 0.60, [
            "rogue_1_relic_p36", "rogue_2_relic_fight_76", "rogue_3_relic_legacy_129",
            "rogue_4_relic_legacy_125", "rogue_5_relic_legacy_68", "rogue_6_relic_legacy_76",
        ]),
    ]
    for professions, hp, ids in groups:
        for relic_id in ids:
            effects = [("hp_pct", hp)]
            if relic_id == "rogue_5_relic_legacy_102":
                effects.append(("def_flat", 100))
            if relic_id == "rogue_5_relic_legacy_103":
                effects.append(("res_flat", 10))
            profession_fix(conn, relic_id, professions, effects)
    profession_fix(conn, "rogue_5_relic_legacy_104", ["辅助", "SUPPORT"], [("hp_pct", 0.40)])

    curse_ids = [
        "rogue_1_relic_p25", "rogue_2_relic_fight_67", "rogue_3_relic_legacy_120",
        "rogue_4_relic_legacy_116",
    ]
    for relic_id in curse_ids:
        profession_fix(conn, relic_id, ["术师", "CASTER"], [("hp_pct", -0.40), ("arts_damage_pct", 0.70)])
    profession_fix(conn, "rogue_5_relic_legacy_109", ["术师", "CASTER"], [("arts_damage_pct", 0.70)])

    for relic_id in ["rogue_3_relic_book_1", "rogue_4_relic_legacy_107", "rogue_5_relic_legacy_60", "rogue_6_relic_legacy_69"]:
        profession_fix(conn, relic_id, ["重装", "TANK"], [("hp_pct", 0.40), ("def_pct", 0.40), ("res_flat", 20)])

    ignored(conn, "rogue_5_relic_legacy_107", "治疗与生命回复、抵抗不属于敌我面板或最终单次伤害模型")


def apply_confirmed_fixes(conn) -> None:
    for relic_id in [
        "rogue_1_relic_sp07", "rogue_2_relic_fight_126", "rogue_3_relic_hand_1",
        "rogue_3_relic_legacy_167", "rogue_4_relic_legacy_153", "rogue_5_relic_return_22",
        "rogue_5_relic_richg_6", "rogue_6_relic_legacy_117",
    ]:
        ignored(conn, relic_id, "事件触发的独立真实伤害不属于最终单次攻击模型，禁止转换普通攻击伤害类型")

    for relic_id in ["rogue_1_relic_c13", "rogue_1_relic_c14", "rogue_1_relic_c16"]:
        reset(conn, relic_id)
        for order, attr in enumerate(("atk_pct", "def_pct", "hp_pct")):
            rule(conn, relic_id, "enemy", attr, 0.10, order=order)

    reset(conn, "rogue_4_relic_curse_3")
    param(conn, "rogue_4_relic_curse_3", "applies", "当前敌人为精英或领袖")
    for order, attr in enumerate(("atk_pct", "def_pct", "hp_pct")):
        rule(conn, "rogue_4_relic_curse_3", "enemy", attr, 0.20, when="applies", order=order)

    for relic_id, base, leader_atk_def, leader_hp in [
        ("rogue_1_relic_c02", 0.30, 0.15, 0.30),
        ("rogue_1_relic_c08", 0.35, 0.20, 0.50),
    ]:
        reset(conn, relic_id)
        param(conn, relic_id, "leader", "当前敌人为领袖")
        for order, attr in enumerate(("atk_pct", "def_pct", "hp_pct")):
            rule(conn, relic_id, "enemy", attr, base, order=order)
        rule(conn, relic_id, "enemy", "atk_pct", leader_atk_def, when="leader", order=3)
        rule(conn, relic_id, "enemy", "def_pct", leader_atk_def, when="leader", order=4)
        rule(conn, relic_id, "enemy", "hp_pct", leader_hp, when="leader", order=5)

    for relic_id in ["rogue_3_relic_fight_18", "rogue_4_relic_legacy_160"]:
        reset(conn, relic_id)
        param(conn, relic_id, "summon_present", "召唤物当前在场")
        rule(conn, relic_id, "operator", "atk_pct", 0.60, when="summon_present")

    duals = [
        ("rogue_2_relic_fight_38", ["特种", "SPECIAL"], 0.30, ["术师", "CASTER"], 0.03),
        ("rogue_2_relic_fight_39", ["术师", "CASTER"], 0.30, ["特种", "SPECIAL"], 0.03),
    ]
    for relic_id, primary, primary_value, secondary, secondary_value in duals:
        reset(conn, relic_id)
        auto_toggle(conn, relic_id, {"profession": primary}, param_id="primary_applies", label="当前干员匹配主要职业")
        auto_toggle(conn, relic_id, {"profession": secondary}, param_id="secondary_applies", label="当前干员匹配次要职业", order=1)
        rule(conn, relic_id, "operator", "atk_pct", primary_value, when="primary_applies", order=0)
        rule(conn, relic_id, "operator", "atk_pct", secondary_value, when="secondary_applies", order=1)

    for relic_id in ["rogue_4_relic_fight_16"]:
        reset(conn, relic_id)
        param(conn, relic_id, "special_stage", "当前关卡为狭路相逢")
        rule(conn, relic_id, "operator", "hp_pct", 0.10, order=0)
        rule(conn, relic_id, "operator", "hp_pct", 0.80, when="special_stage", order=1)
    reset(conn, "rogue_4_relic_fight_18")
    param(conn, "rogue_4_relic_fight_18", "special_stage", "当前关卡为险路恶敌")
    for order, attr in enumerate(("atk_pct", "hp_pct")):
        rule(conn, "rogue_4_relic_fight_18", "operator", attr, 0.10, order=order)
        rule(conn, "rogue_4_relic_fight_18", "operator", attr, 0.20, when="special_stage", order=order + 2)
    reset(conn, "rogue_6_relic_fight_25")
    rule(conn, "rogue_6_relic_fight_25", "operator", "atk_pct", 0.30, order=0)
    rule(conn, "rogue_6_relic_fight_25", "operator", "hp_pct", 0.30, order=1)


def apply_conditional_fixes(conn) -> None:
    for relic_id, value in [
        ("rogue_1_relic_p30", -20), ("rogue_2_relic_fight_71", -20),
        ("rogue_3_relic_legacy_124", -20), ("rogue_4_relic_legacy_120", -20),
        ("rogue_5_relic_legacy_96", -30),
    ]:
        reset(conn, relic_id)
        param(conn, relic_id, "in_range", "当前敌人在辅助干员攻击范围内")
        rule(conn, relic_id, "enemy", "def_pct", value / 100, when="in_range", order=0)
        rule(conn, relic_id, "enemy", "res_flat", value, when="in_range", order=1)

    reset(conn, "rogue_2_relic_fight_155")
    param(conn, "rogue_2_relic_fight_155", "count", "场上术师数量", param_type="number", maximum=20)
    rule(conn, "rogue_2_relic_fight_155", "enemy", "res_flat", expr="count*-12")

    reset(conn, "rogue_6_relic_legacy_73")
    param(conn, "rogue_6_relic_legacy_73", "count", "场上术师数量", param_type="number", maximum=8)
    rule(conn, "rogue_6_relic_legacy_73", "operator", "arts_damage_pct", expr="count*0.12")

    for relic_id in ["rogue_5_relic_legacy_97", "rogue_6_relic_legacy_65"]:
        reset(conn, relic_id)
        auto_toggle(conn, relic_id, {"profession": ["先锋", "PIONEER"]})
        param(conn, relic_id, "first_60_seconds", "当前处于战斗开始60秒内", order=1)
        for order, attr in enumerate(("atk_pct", "def_pct")):
            rule(conn, relic_id, "operator", attr, expr="1.0*applies*first_60_seconds", order=order)

    ignored(conn, "rogue_2_relic_grace_86", "效果目标为特殊友方单位猎潮的骑士，不属于当前干员面板")
    for relic_id in ["rogue_4_relic_legacy_186", "rogue_5_relic_legacy_46", "rogue_5_relic_fight_3", "rogue_6_relic_legacy_134"]:
        ignored(conn, relic_id, "效果仅作用召唤物，当前模型不计算召唤物独立面板")

    reset(conn, "rogue_3_relic_fight_33")
    param(conn, "rogue_3_relic_fight_33", "in_domain", "当前敌人处于国度中")
    rule(conn, "rogue_3_relic_fight_33", "enemy", "aspd", -30, when="in_domain")

    reset(conn, "rogue_4_relic_fight_3")
    param(conn, "rogue_4_relic_fight_3", "enemy_is_sarkaz", "当前敌人为萨卡兹")
    rule(conn, "rogue_4_relic_fight_3", "operator", "phys_damage_pct", 0.50, when="enemy_is_sarkaz", order=0)
    rule(conn, "rogue_4_relic_fight_3", "operator", "arts_damage_pct", 0.50, when="enemy_is_sarkaz", order=1)

    subprofession_fix(conn, "rogue_5_relic_custog_10", ["伺烛客"], [("atk_pct", 0.50), ("def_pct", 0.50)])
    reset(conn, "rogue_5_relic_custog_11")
    auto_toggle(conn, "rogue_5_relic_custog_11", {"sub_profession_cn_any": ["伺烛客"]})
    param(conn, "rogue_5_relic_custog_11", "count", "编队中伺烛客数量", param_type="number", maximum=12, order=1)
    for order, attr in enumerate(("atk_pct", "hp_pct", "def_pct")):
        rule(conn, "rogue_5_relic_custog_11", "operator", attr, expr="count*0.10*applies", order=order)
    reset(conn, "rogue_5_relic_explore_6")
    auto_toggle(conn, "rogue_5_relic_explore_6", {"sub_profession_cn_any": ["伺烛客"]})
    param(conn, "rogue_5_relic_explore_6", "count", "编队中伺烛客数量", param_type="number", maximum=10, order=1)
    rule(conn, "rogue_5_relic_explore_6", "operator", "aspd", expr="count*5*applies")
    for relic_id, base, extra in [
        ("rogue_5_relic_legacy_92", 0.20, 0.10), ("rogue_5_relic_legacy_93", 0.50, 0.30),
    ]:
        reset(conn, relic_id)
        auto_toggle(conn, relic_id, {"sub_profession_cn_any": ["伺烛客"]})
        rule(conn, relic_id, "operator", "hp_pct", base, order=0)
        rule(conn, relic_id, "operator", "hp_pct", extra, when="applies", order=1)
    subprofession_fix(conn, "rogue_5_relic_speg_1", ["伺烛客"], [("atk_pct", 0.40)])

    reset(conn, "rogue_4_relic_book_8")
    auto_toggle(conn, "rogue_4_relic_book_8", {"profession": ["重装", "TANK"]})
    param(conn, "rogue_4_relic_book_8", "count", "仅在诡谲断章生效的收藏品数量", param_type="number", maximum=99, order=1)
    rule(conn, "rogue_4_relic_book_8", "operator", "def_pct", expr="count*0.20*applies", order=0)
    rule(conn, "rogue_4_relic_book_8", "operator", "hp_pct", expr="count*0.30*applies", order=1)
    reset(conn, "rogue_5_relic_custog_2")
    auto_toggle(conn, "rogue_5_relic_custog_2", {"position": "MELEE"})
    rule(conn, "rogue_5_relic_custog_2", "operator", "def_pct", 0.50, when="applies")
    profession_fix(conn, "rogue_5_relic_richg_3", ["先锋", "PIONEER"], [("atk_pct", 0.25)])


def apply_hand_fixes(conn) -> None:
    # Existing v4 hand rules are correct for panel stats. Only expand the paired cap.
    conn.execute(
        text("UPDATE relic_condition_params SET max_value=8,label='在场叠层（无配套最高5，有锈刃-久居最高8）',rule_version=:v WHERE relic_id='rogue_4_relic_hand_4' AND param_id='stacks'"),
        {"v": VERSION},
    )

    reset(conn, "rogue_6_relic_hand_3")
    auto_toggle(conn, "rogue_6_relic_hand_3", {"sub_profession_cn_any": ["铁卫", "哨戒铁卫", "不屈者"]})
    param(conn, "rogue_6_relic_hand_3", "bonus_pct", "当前剩余攻击/生命加成", param_type="number", maximum=100, unit="%", order=1)
    rule(conn, "rogue_6_relic_hand_3", "operator", "atk_pct", expr="bonus_pct/100*applies", order=0)
    rule(conn, "rogue_6_relic_hand_3", "operator", "hp_pct", expr="bonus_pct/100*applies", order=1)

    subprofession_fix(
        conn,
        "rogue_6_relic_hand_4",
        ["炮手", "散射手", "裂空炮手"],
        [("atk_pct", 1.50)],
        condition=("skill_window", "当前处于技能开启后5秒内"),
    )

    reset(conn, "rogue_6_relic_hand_5")
    auto_toggle(conn, "rogue_6_relic_hand_5", {"sub_profession_cn_any": ["轰击术师", "链术师", "驭械术师"]})
    param(conn, "rogue_6_relic_hand_5", "stacks", "伤害后攻击力叠层", param_type="number", maximum=5, order=1)
    rule(conn, "rogue_6_relic_hand_5", "operator", "atk_pct", expr="stacks*0.20*applies")


def apply_user_reported_fixes(conn) -> None:
    """2026-08-04 用户复核：敌人类型、叠层和类型伤害规则。"""
    # 探测先锋：每层只强化猎犬 proto 敌人的生命与攻击。
    rid = "rogue_6_relic_fight_30"
    reset(conn, rid)
    param(conn, rid, "enemy_is_hound_proto", "当前敌人为猎犬proto")
    param(conn, rid, "stacks", "完成“追猎”作战层数", param_type="number", maximum=99, order=1)
    rule(conn, rid, "enemy", "hp_pct", expr="stacks*0.20*enemy_is_hound_proto", order=0)
    rule(conn, rid, "enemy", "atk_pct", expr="stacks*0.20*enemy_is_hound_proto", order=1)

    # 厄运火杆：居民战的生命降低与胜利次数攻速叠层是两个独立条件。
    rid = "rogue_6_relic_cargo_11"
    reset(conn, rid)
    param(conn, rid, "enemy_is_resident", "当前敌人为“居民”")
    param(conn, rid, "stacks", "此前作战胜利层数", param_type="number", maximum=99, order=1)
    rule(conn, rid, "enemy", "hp_pct", -0.40, when="enemy_is_resident", order=0)
    rule(conn, rid, "operator", "aspd", expr="stacks*10", order=1)

    # 犬植浆：当前干员被多少名持有者的攻击范围覆盖。
    rid = "rogue_6_relic_artifact_4"
    reset(conn, rid)
    param(conn, rid, "stacks", "覆盖当前干员的犬植浆层数", param_type="number", maximum=99)
    rule(conn, rid, "operator", "atk_pct", expr="stacks*0.10")

    # 猎印：猎犬 proto 降攻；探测先锋层数为我方提供法抗。
    rid = "rogue_6_relic_cargo_12"
    reset(conn, rid)
    param(conn, rid, "enemy_is_hound_proto", "当前敌人为猎犬proto")
    param(conn, rid, "scout_stacks", "拥有的探测先锋层数", param_type="number", maximum=99, order=1)
    rule(conn, rid, "enemy", "atk_pct", -0.50, when="enemy_is_hound_proto", order=0)
    rule(conn, rid, "operator", "res_flat", expr="scout_stacks*10", order=1)

    # 阿猛只提高元素伤害；文明的存续只提高真实伤害。
    for rid in ("rogue_5_relic_fight_4", "rogue_6_relic_legacy_104"):
        reset(conn, rid)
        rule(conn, rid, "operator", "elemental_damage_pct", 1.00)
    for rid in (
        "rogue_1_relic_q32", "rogue_2_relic_fight_117", "rogue_3_relic_legacy_161",
        "rogue_4_relic_legacy_149", "rogue_5_relic_legacy_19", "rogue_6_relic_legacy_11",
    ):
        reset(conn, rid)
        rule(conn, rid, "operator", "true_damage_pct", 1.50)


def apply_rogue6_audit_fixes(conn) -> None:
    """沉沦者的黑流树海 239 件全量审计确认项。"""
    rid = "rogue_6_relic_legacy_121"  # 万星园之辉
    reset(conn, rid)
    param(conn, rid, "trigger_window", "当前处于浮空/失重状态变化后的10秒内")
    rule(conn, rid, "operator", "damage_pct", 0.30, when="trigger_window")

    rid = "rogue_6_relic_legacy_124"  # 黑色郁金香
    reset(conn, rid)
    param(conn, rid, "bonus_pct", "当前逐渐提升的攻击力加成", param_type="number", maximum=60, unit="%")
    rule(conn, rid, "operator", "atk_pct", expr="bonus_pct/100")

    rid = "rogue_6_relic_fight_18"  # 翱翼
    reset(conn, rid)
    param(conn, rid, "operator_airborne", "当前干员处于起飞状态")
    param(conn, rid, "airborne_count", "我方起飞单位数量", param_type="number", maximum=99, order=1)
    rule(conn, rid, "operator", "atk_pct", expr="airborne_count*0.25*operator_airborne")

    rid = "rogue_6_relic_fight_19"  # 虬蜕
    reset(conn, rid)
    param(conn, rid, "ground_count", "我方未起飞单位数量", param_type="number", maximum=99)
    rule(conn, rid, "operator", "def_pct", expr="ground_count*0.10")

    rid = "rogue_6_relic_fight_21"  # 冰中火
    reset(conn, rid)
    rule(conn, rid, "operator", "elemental_damage_pct", 0.75)

    rid = "rogue_6_relic_fight_23"  # 猎犬病特效药
    reset(conn, rid)
    param(conn, rid, "frenzy_burst", "当前处于狂躁元素爆发期间")
    rule(conn, rid, "operator", "aspd", 50, when="frenzy_burst")

    rid = "rogue_6_relic_fight_26"  # 竞技场贵宾券
    reset(conn, rid)
    param(conn, rid, "enemy_is_elite", "当前敌人为精英敌人")
    rule(conn, rid, "enemy", "hp_pct", 0.10, when="enemy_is_elite")

    rid = "rogue_6_relic_assign_11"  # “老妈的鼓励”
    reset(conn, rid)
    param(conn, rid, "first_deployment", "当前为目标干员首次部署")
    rule(conn, rid, "operator", "atk_pct", 0.50, when="first_deployment")

    rid = "rogue_6_relic_cargo_2"  # 悲伤的红
    reset(conn, rid)
    param(conn, rid, "part_count", "零件箱中的零件数量", param_type="number", maximum=99)
    rule(conn, rid, "operator", "atk_pct", expr="part_count*0.08", order=0)
    rule(conn, rid, "operator", "hp_pct", expr="part_count*0.08", order=1)

    ignored(conn, "rogue_6_relic_book_6", "仅增加阻挡数，不影响敌我面板或最终伤害")
    ignored(conn, "rogue_6_relic_legacy_94", "仅影响探索失败续行流程，不影响敌我面板或最终伤害")


# ---------------------------------------------------------------------------
# Pending review fixes (VERSION 5): 118 relics / 159 rules
# ---------------------------------------------------------------------------


def _approve_existing_rules(conn, relic_ids: list[str], note: str = "pending review fix v5") -> None:
    """Bulk-approve existing pending rules by setting review_status='approved'."""
    if not relic_ids:
        return
    conn.execute(
        text(
            """
            UPDATE relic_effect_rules SET review_status='approved', rule_version=:v,
              reviewed_at=NOW(), note=:note
            WHERE relic_id IN :ids AND review_status<>'approved'
            """
        ),
        {"v": VERSION, "ids": tuple(relic_ids), "note": note},
    )


def _get_approved_twin_rules(conn, relic_id: str) -> list[dict] | None:
    """Find an approved twin relic (same name, same usage_text)."""
    row = conn.execute(
        text(
            """
            SELECT twin.id AS twin_id, twin.name AS twin_name
            FROM relics r
            JOIN relics twin ON twin.name = r.name AND twin.id <> r.id
              AND COALESCE(twin.usage_text, '') = COALESCE(r.usage_text, '')
            JOIN relic_effect_rules approved ON approved.relic_id = twin.id
            WHERE r.id = :rid
              AND approved.review_status = 'approved'
              AND approved.calculation_status = 'active'
            LIMIT 1
            """
        ),
        {"rid": relic_id},
    ).mappings().first()
    if not row:
        return None
    twin_id = row["twin_id"]
    rules = conn.execute(
        text(
            """
            SELECT target, attr, operation, value, value_expr, when_param,
                   display_order, note
            FROM relic_effect_rules
            WHERE relic_id = :tid AND review_status = 'approved'
              AND calculation_status = 'active'
            ORDER BY display_order, id
            """
        ),
        {"tid": twin_id},
    ).mappings().all()
    params = conn.execute(
        text(
            """
            SELECT param_id, param_type, label, default_value, min_value,
                   max_value, step_value, unit, auto_rule, display_order
            FROM relic_condition_params
            WHERE relic_id = :tid AND review_status = 'approved'
            ORDER BY display_order, param_id
            """
        ),
        {"tid": twin_id},
    ).mappings().all()
    return [dict(r) for r in rules], [dict(p) for p in params]


def _copy_twin_rules(conn, relic_id: str, twin_rules: list[dict], twin_params: list[dict]) -> None:
    """Reset pending relic and copy approved twin's rules and params."""
    reset(conn, relic_id)
    for r in twin_rules:
        conn.execute(
            text(
                """
                INSERT INTO relic_effect_rules(
                  relic_id, target, attr, operation, value, value_expr, when_param,
                  calculation_status, source, rule_version, review_status,
                  display_order, note, reviewed_at
                ) VALUES(:rid, :target, :attr, :operation, :value, :expr, :when,
                  'active', 'manual', :version, 'approved', :ord, :note, NOW())
                """
            ),
            {
                "rid": relic_id,
                "target": r["target"],
                "attr": r["attr"],
                "operation": r.get("operation", "add"),
                "value": r.get("value", 0),
                "expr": r.get("value_expr"),
                "when": r.get("when_param"),
                "version": VERSION,
                "ord": r.get("display_order", 0),
                "note": f"twin copy from approved {r.get('note', '')}",
            },
        )
    for p in twin_params:
        auto_rule = p.get("auto_rule")
        if isinstance(auto_rule, str):
            auto_rule = json.loads(auto_rule) if auto_rule else None
        param(
            conn, relic_id, p["param_id"], p.get("label", ""),
            param_type=p.get("param_type", "toggle"),
            default=float(p.get("default_value", 0)),
            minimum=p.get("min_value"),
            maximum=p.get("max_value"),
            step=p.get("step_value"),
            unit=p.get("unit"),
            auto=auto_rule,
            order=p.get("display_order", 0),
        )


def _apply_twin_copies(conn) -> int:
    """Phase 1: copy approved twin rules to pending relics. Returns count fixed."""
    pending_twins = conn.execute(
        text(
            """
            SELECT DISTINCT r.id AS relic_id
            FROM relics r
            JOIN relic_effect_rules rr ON rr.relic_id = r.id
            JOIN relics twin ON twin.name = r.name AND twin.id <> r.id
              AND COALESCE(twin.usage_text, '') = COALESCE(r.usage_text, '')
            JOIN relic_effect_rules approved ON approved.relic_id = twin.id
            WHERE rr.review_status <> 'approved'
              AND rr.calculation_status = 'active'
              AND approved.review_status = 'approved'
              AND approved.calculation_status = 'active'
            """
        )
    ).mappings().all()
    seen: set[str] = set()
    for row in pending_twins:
        rid = row["relic_id"]
        if rid in seen:
            continue
        twin_data = _get_approved_twin_rules(conn, rid)
        if twin_data:
            seen.add(rid)
            twin_rules, twin_params = twin_data
            _copy_twin_rules(conn, rid, twin_rules, twin_params)
    return len(seen)


def _fix_rogue1_curse_relics(conn) -> None:
    """rogue_1 curse relics: only enemies are buffed, not operators.

    All of these relics describe "所有敌方单位" (all enemy units) in their
    usage text.  The old parsed rules incorrectly applied HP% and DEF% to
    operators as well — that was a text-parsing bug.
    """
    # c05/c11 were approved by a previous migration audit with operator rules
    # that contradict the description.  Reset and rebuild them too.
    curse_values = {
        "rogue_1_relic_c03": 0.30,
        "rogue_1_relic_c04": 0.25,
        "rogue_1_relic_c05": 0.25,  # 浅眠好梦 — was wrongly approved with operator rules
        "rogue_1_relic_c06": 0.30,
        "rogue_1_relic_c07": 0.35,
        "rogue_1_relic_c09": 0.35,
        "rogue_1_relic_c10": 0.30,
        "rogue_1_relic_c11": 0.30,  # 浅眠好梦（重铸）— was wrongly approved with operator rules
        "rogue_1_relic_c12": 0.35,
    }
    for relic_id, value in curse_values.items():
        reset(conn, relic_id)
        for order, attr in enumerate(("atk_pct", "def_pct", "hp_pct")):
            rule(conn, relic_id, "enemy", attr, value, order=order,
                 note="pending review fix v5: curse relic enemy-only buff")

    # 乌萨斯弯刀（重铸）: base 35% + 10% per floor, emergency -5% (min 35%)
    reset(conn, "rogue_1_relic_c07")
    param(conn, "rogue_1_relic_c07", "floors", "已进入新一层数（每层+10%）",
          param_type="number", maximum=99)
    param(conn, "rogue_1_relic_c07", "emergency_count", "完成紧急作战次数（每次-5%，最低35%）",
          param_type="number", maximum=99, order=1)
    rule(conn, "rogue_1_relic_c07", "enemy", "atk_pct",
         expr="max(0.35, 0.35+floors*0.10-emergency_count*0.05)", order=0,
         note="pending review fix v5: floor-scaling enemy buff")
    rule(conn, "rogue_1_relic_c07", "enemy", "def_pct",
         expr="max(0.35, 0.35+floors*0.10-emergency_count*0.05)", order=1,
         note="pending review fix v5: floor-scaling enemy buff")
    rule(conn, "rogue_1_relic_c07", "enemy", "hp_pct",
         expr="max(0.35, 0.35+floors*0.10-emergency_count*0.05)", order=2,
         note="pending review fix v5: floor-scaling enemy buff")


def _fix_simple_permanent_stats(conn) -> None:
    """Relics with simple permanent operator stats, no conditions."""
    simple_ids = [
        "rogue_1_relic_m05",       # 断剑: hp_pct -0.3
        "rogue_2_relic_fight_41",  # 分浪: hp_pct -0.25
        "rogue_3_relic_fight_6",   # 永夜的窥视: atk_pct +25%, aspd +25
        "rogue_3_relic_fight_7",   # 枯木的回声: hp_pct -25%
        "rogue_3_relic_explore_6", # 安玛的爱: atk/hp/def +1%
    ]
    _approve_existing_rules(conn, simple_ids)

    # 决心: needs res_flat +20 added
    reset(conn, "rogue_2_relic_grace_88")
    for order, (attr, value) in enumerate([
        ("hp_pct", 1.20), ("def_pct", 1.20), ("res_flat", 20),
    ]):
        rule(conn, "rogue_2_relic_grace_88", "operator", attr, value, order=order,
             note="pending review fix v5")


def _approve_series_relics(conn) -> None:
    """Bulk-approve terrain/shell/forest/church series across rogue_2–rogue_6."""
    # 地形图: "可同时部署人数+1, 所有我方单位的防御力+X%"
    terrain = [
        "rogue_2_relic_grace_7",
        "rogue_3_relic_legacy_16", "rogue_3_relic_legacy_16_a", "rogue_3_relic_legacy_16_b",
        "rogue_4_relic_legacy_15", "rogue_4_relic_legacy_15_a", "rogue_4_relic_legacy_15_b", "rogue_4_relic_legacy_15_c",
        "rogue_5_relic_legacy_33", "rogue_5_relic_legacy_33_a", "rogue_5_relic_legacy_33_b", "rogue_5_relic_legacy_33_c",
        "rogue_6_relic_legacy_28", "rogue_6_relic_legacy_28_a", "rogue_6_relic_legacy_28_b", "rogue_6_relic_legacy_28_c",
    ]
    # 神音海螺: "可同时部署人数+1, 所有我方单位的生命值+X%"
    shell = [
        "rogue_2_relic_grace_8",
        "rogue_3_relic_legacy_17", "rogue_3_relic_legacy_17_a", "rogue_3_relic_legacy_17_b",
        "rogue_4_relic_legacy_16", "rogue_4_relic_legacy_16_a", "rogue_4_relic_legacy_16_b", "rogue_4_relic_legacy_16_c",
        "rogue_5_relic_legacy_34", "rogue_5_relic_legacy_34_a", "rogue_5_relic_legacy_34_b", "rogue_5_relic_legacy_34_c",
        "rogue_6_relic_legacy_29", "rogue_6_relic_legacy_29_a", "rogue_6_relic_legacy_29_b", "rogue_6_relic_legacy_29_c",
    ]
    # 林间夜话: "可同时部署人数+2, 所有我方单位的防御力+X%"
    forest = [
        "rogue_2_relic_grace_9",
        "rogue_3_relic_legacy_18", "rogue_3_relic_legacy_18_a", "rogue_3_relic_legacy_18_b",
        "rogue_4_relic_legacy_17", "rogue_4_relic_legacy_17_a", "rogue_4_relic_legacy_17_b", "rogue_4_relic_legacy_17_c",
        "rogue_5_relic_legacy_35", "rogue_5_relic_legacy_35_a", "rogue_5_relic_legacy_35_b", "rogue_5_relic_legacy_35_c",
        "rogue_6_relic_legacy_30", "rogue_6_relic_legacy_30_a", "rogue_6_relic_legacy_30_b", "rogue_6_relic_legacy_30_c",
    ]
    # 教堂救济餐券: "可同时部署人数+2, 所有我方单位的生命值+X%"
    church = [
        "rogue_2_relic_grace_10",
        "rogue_3_relic_legacy_19", "rogue_3_relic_legacy_19_a", "rogue_3_relic_legacy_19_b",
        "rogue_4_relic_legacy_18", "rogue_4_relic_legacy_18_a", "rogue_4_relic_legacy_18_b", "rogue_4_relic_legacy_18_c",
        "rogue_5_relic_legacy_36", "rogue_5_relic_legacy_36_a", "rogue_5_relic_legacy_36_b", "rogue_5_relic_legacy_36_c",
        "rogue_6_relic_legacy_31", "rogue_6_relic_legacy_31_a", "rogue_6_relic_legacy_31_b", "rogue_6_relic_legacy_31_c",
    ]
    all_series = terrain + shell + forest + church
    _approve_existing_rules(conn, all_series, note="series relic v5: deployment count is meta, stat is permanent")


def _fix_stacking_relics(conn) -> None:
    """Relics needing number-type params with per-unit stacking expressions."""
    # 蓝卡坞安全衣: per 遭诅古物 def%+25, res_flat+10
    reset(conn, "rogue_2_relic_fight_142")
    param(conn, "rogue_2_relic_fight_142", "cursed_count", "当前拥有遭诅古物数量",
          param_type="number", maximum=99)
    rule(conn, "rogue_2_relic_fight_142", "operator", "def_pct", expr="cursed_count*0.25", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_2_relic_fight_142", "operator", "res_flat", expr="cursed_count*10", order=1,
         note="pending review fix v5")

    # 刀光剑影: per 遭诅古物 aspd+35
    reset(conn, "rogue_2_relic_fight_143")
    param(conn, "rogue_2_relic_fight_143", "cursed_count", "当前拥有遭诅古物数量",
          param_type="number", maximum=99)
    rule(conn, "rogue_2_relic_fight_143", "operator", "aspd", expr="cursed_count*35",
         note="pending review fix v5")

    # 断杖-和声 (rogue_3): per 术师 arts_damage+12% (max 8)
    reset(conn, "rogue_3_relic_book_7")
    param(conn, "rogue_3_relic_book_7", "count", "场上术师数量", param_type="number", maximum=8)
    rule(conn, "rogue_3_relic_book_7", "operator", "arts_damage_pct", expr="count*0.12",
         note="pending review fix v5")

    # 断杖-波纹 (rogue_4/5): same pattern as rogue_6_relic_legacy_73
    for relic_id in ["rogue_4_relic_book_3", "rogue_5_relic_legacy_47"]:
        reset(conn, relic_id)
        param(conn, relic_id, "count", "场上术师数量", param_type="number", maximum=8)
        rule(conn, relic_id, "operator", "arts_damage_pct", expr="count*0.12",
             note="pending review fix v5")

    # 束灵骨 (rogue_4): per 思绪 atk+3%
    reset(conn, "rogue_4_relic_fight_21")
    param(conn, "rogue_4_relic_fight_21", "thought_count", "当前携带思绪数量",
          param_type="number", maximum=99)
    rule(conn, "rogue_4_relic_fight_21", "operator", "atk_pct", expr="thought_count*0.03",
         note="pending review fix v5")

    # 生命熔炉之薪 (rogue_4): per 思绪 atk+5%
    reset(conn, "rogue_4_relic_fight_22")
    param(conn, "rogue_4_relic_fight_22", "thought_count", "当前携带思绪数量",
          param_type="number", maximum=99)
    rule(conn, "rogue_4_relic_fight_22", "operator", "atk_pct", expr="thought_count*0.05",
         note="pending review fix v5")

    # 青涩眷恋 (rogue_4): per 思绪 hp+3%, def+3%
    reset(conn, "rogue_4_relic_fight_25")
    param(conn, "rogue_4_relic_fight_25", "thought_count", "当前携带思绪数量",
          param_type="number", maximum=99)
    rule(conn, "rogue_4_relic_fight_25", "operator", "hp_pct", expr="thought_count*0.03", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_4_relic_fight_25", "operator", "def_pct", expr="thought_count*0.03", order=1,
         note="pending review fix v5")

    # 咒仪溯兽 (rogue_4): base 5 aspd + stacking 5 per layer (max 10 layers)
    reset(conn, "rogue_4_relic_fight_26")
    param(conn, "rogue_4_relic_fight_26", "stacks", "灵感消耗层数（可叠加10次）",
          param_type="number", maximum=10)
    rule(conn, "rogue_4_relic_fight_26", "operator", "aspd", expr="5+stacks*5",
         note="pending review fix v5")

    # 琥珀伤痕 (rogue_3): per excess 抗干扰指数 hp+8%, atk+8%
    reset(conn, "rogue_3_relic_res_12")
    param(conn, "rogue_3_relic_res_12", "excess", "抗干扰指数超出上限点数",
          param_type="number", maximum=99)
    rule(conn, "rogue_3_relic_res_12", "operator", "atk_pct", expr="excess*0.08", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_3_relic_res_12", "operator", "hp_pct", expr="excess*0.08", order=1,
         note="pending review fix v5")

    # 酿山河 (rogue_5): per 花钱 atk+10%, hp+20%
    reset(conn, "rogue_5_relic_speg_4")
    param(conn, "rogue_5_relic_speg_4", "coin_count", "钱盒内花钱数量",
          param_type="number", maximum=99)
    rule(conn, "rogue_5_relic_speg_4", "operator", "atk_pct", expr="coin_count*0.10", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_5_relic_speg_4", "operator", "hp_pct", expr="coin_count*0.20", order=1,
         note="pending review fix v5")

    # 家常小炒 (rogue_5): base 20% + 10% per combat
    reset(conn, "rogue_5_relic_explore_3")
    param(conn, "rogue_5_relic_explore_3", "combat_count", "已通过岁兽残识战斗场次",
          param_type="number", maximum=99)
    rule(conn, "rogue_5_relic_explore_3", "operator", "atk_pct", expr="0.20+combat_count*0.10", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_5_relic_explore_3", "operator", "hp_pct", expr="0.20+combat_count*0.10", order=1,
         note="pending review fix v5")

    # 仇名录 (rogue_6): base 2% + 0.2% per kill (max +200%)
    reset(conn, "rogue_6_relic_artifact_7")
    param(conn, "rogue_6_relic_artifact_7", "bonus_pct", "当前永久攻击力额外加成",
          param_type="number", maximum=200, unit="%")
    rule(conn, "rogue_6_relic_artifact_7", "operator", "atk_pct", expr="0.02+bonus_pct/100",
         note="pending review fix v5")

    # 近卫军帽 (rogue_1): per deployment hp+25%
    reset(conn, "rogue_1_relic_sp02")
    param(conn, "rogue_1_relic_sp02", "deploy_count", "本局战斗中部署次数",
          param_type="number", maximum=99)
    rule(conn, "rogue_1_relic_sp02", "operator", "hp_pct", expr="deploy_count*0.25",
         note="pending review fix v5")


def _fix_hp_threshold_relics(conn) -> None:
    """HP-threshold scaling relics: bonus_pct number param + expr."""
    # 古乔治营养原浆 (rogue_2/4/5): HP越高ATK越高, max +30%
    for relic_id in ["rogue_2_relic_fight_140", "rogue_4_relic_legacy_181", "rogue_5_relic_return_20"]:
        reset(conn, relic_id)
        param(conn, relic_id, "bonus_pct", "当前根据生命值获得的攻击力加成",
              param_type="number", maximum=30, unit="%")
        rule(conn, relic_id, "operator", "atk_pct", expr="bonus_pct/100",
             note="pending review fix v5: HP% to ATK%")

    # 紧急活性剂 (rogue_2/4/5/6): HP越低ASPD越快, max +60 (rogue_6: +100)
    for relic_id, max_val in [
        ("rogue_2_relic_fight_141", 60), ("rogue_4_relic_legacy_182", 60),
        ("rogue_5_relic_return_19", 60), ("rogue_6_relic_legacy_102", 100),
    ]:
        reset(conn, relic_id)
        param(conn, relic_id, "bonus_aspd", "当前根据生命值获得的攻击速度加成",
              param_type="number", maximum=max_val)
        rule(conn, relic_id, "operator", "aspd", expr="bonus_aspd",
             note="pending review fix v5: HP% to ASPD")

    # 热辣可可 (rogue_6): HP越低ATK越高, max +150%
    reset(conn, "rogue_6_relic_fight_14")
    param(conn, "rogue_6_relic_fight_14", "bonus_pct", "当前根据生命值获得的攻击力加成",
          param_type="number", maximum=150, unit="%")
    rule(conn, "rogue_6_relic_fight_14", "operator", "atk_pct", expr="bonus_pct/100",
         note="pending review fix v5: HP% to ATK%")


def _fix_conditional_toggle_relics(conn) -> None:
    """Relics needing toggle params with when-conditions."""
    # 噤声 (rogue_1): same usage_text as 黑色郁金香 — 技能未开启时攻击力逐渐提升
    reset(conn, "rogue_1_relic_n15")
    param(conn, "rogue_1_relic_n15", "bonus_pct", "当前逐渐提升的攻击力加成",
          param_type="number", maximum=60, unit="%")
    rule(conn, "rogue_1_relic_n15", "operator", "atk_pct", expr="bonus_pct/100",
         note="pending review fix v5")

    # 深蓝之树 (rogue_2): unconditional enemy.aspd+15, just approve
    _approve_existing_rules(conn, ["rogue_2_relic_curse_10"],
                            note="pending review fix v5: unconditional enemy aspd")

    # 遗落之帜 (rogue_2): random chosen tile
    reset(conn, "rogue_2_relic_fight_128")
    param(conn, "rogue_2_relic_fight_128", "on_chosen_tile", "当前干员位于本局随机选中位置")
    rule(conn, "rogue_2_relic_fight_128", "operator", "atk_pct", 0.50, when="on_chosen_tile", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_2_relic_fight_128", "operator", "aspd", 50, when="on_chosen_tile", order=1,
         note="pending review fix v5")

    # 丝契之谜 (rogue_4): no adjacent ops → aspd+50
    reset(conn, "rogue_4_relic_encounter_8")
    param(conn, "rogue_4_relic_encounter_8", "no_adjacent_ops", "当前干员周围8格不存在其他干员")
    rule(conn, "rogue_4_relic_encounter_8", "operator", "aspd", 50, when="no_adjacent_ops",
         note="pending review fix v5")

    # 死仇时代的恨意 (rogue_4): missing operator.atk_pct, both sides +20%
    reset(conn, "rogue_4_relic_explore_3")
    rule(conn, "rogue_4_relic_explore_3", "operator", "atk_pct", 0.20, order=0,
         note="pending review fix v5")
    rule(conn, "rogue_4_relic_explore_3", "enemy", "atk_pct", 0.20, order=1,
         note="pending review fix v5")

    # 无封长盒 (rogue_5): fix operator.aspd→enemy, add elite/leader toggle
    reset(conn, "rogue_5_relic_final_5")
    param(conn, "rogue_5_relic_final_5", "enemy_is_elite_leader", "当前敌人为精英或领袖")
    rule(conn, "rogue_5_relic_final_5", "enemy", "def_pct", 0.30, when="enemy_is_elite_leader", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_5_relic_final_5", "enemy", "aspd", 20, when="enemy_is_elite_leader", order=1,
         note="pending review fix v5")

    # 四方绘料 (rogue_5): 4 deployed → next deploy gets buff
    reset(conn, "rogue_5_relic_cardg_1")
    param(conn, "rogue_5_relic_cardg_1", "is_next_deploy", "当前干员为已部署4名后的下一名干员")
    rule(conn, "rogue_5_relic_cardg_1", "operator", "hp_pct", 0.50, when="is_next_deploy", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_5_relic_cardg_1", "operator", "def_pct", 0.50, when="is_next_deploy", order=1,
         note="pending review fix v5")

    # 四时丹青毫 (rogue_5): same pattern
    reset(conn, "rogue_5_relic_cardg_2")
    param(conn, "rogue_5_relic_cardg_2", "is_next_deploy", "当前干员为已部署4名后的下一名干员")
    rule(conn, "rogue_5_relic_cardg_2", "operator", "atk_pct", 0.50, when="is_next_deploy",
         note="pending review fix v5")

    # 艺影 (rogue_5): leftmost in deployment queue
    reset(conn, "rogue_5_relic_cardg_5")
    param(conn, "rogue_5_relic_cardg_5", "is_leftmost_deploy", "当前干员为待部署区最左侧单位")
    rule(conn, "rogue_5_relic_cardg_5", "operator", "atk_pct", 0.30, when="is_leftmost_deploy", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_5_relic_cardg_5", "operator", "aspd", 30, when="is_leftmost_deploy", order=1,
         note="pending review fix v5")

    # 商影 (rogue_5): rightmost in deployment queue
    reset(conn, "rogue_5_relic_cardg_6")
    param(conn, "rogue_5_relic_cardg_6", "is_rightmost_deploy", "当前干员为待部署区最右侧单位")
    rule(conn, "rogue_5_relic_cardg_6", "operator", "hp_pct", 0.50, when="is_rightmost_deploy", order=0,
         note="pending review fix v5")
    rule(conn, "rogue_5_relic_cardg_6", "operator", "def_pct", 0.50, when="is_rightmost_deploy", order=1,
         note="pending review fix v5")

    # 封神令 (rogue_5): near intrusion point
    reset(conn, "rogue_5_relic_fight_1")
    param(conn, "rogue_5_relic_fight_1", "near_intrusion", "当前干员部署在侵入点周围8格")
    rule(conn, "rogue_5_relic_fight_1", "operator", "atk_pct", 1.00, when="near_intrusion",
         note="pending review fix v5")

    # 奔兽战车 (rogue_5): DP ≥ 99
    reset(conn, "rogue_5_relic_richg_4")
    param(conn, "rogue_5_relic_richg_4", "high_cost", "当前部署费用为99及以上")
    rule(conn, "rogue_5_relic_richg_4", "operator", "hp_pct", 0.50, when="high_cost",
         note="pending review fix v5")

    # 襁褓九头蛇 (rogue_6): enemy atk+30% hp+30%, per-region operator atk+10% hp+10%
    reset(conn, "rogue_6_start_4")
    param(conn, "rogue_6_start_4", "region_count", "已进入新区域次数",
          param_type="number", maximum=99)
    rule(conn, "rogue_6_start_4", "enemy", "atk_pct", 0.30, order=0,
         note="pending review fix v5")
    rule(conn, "rogue_6_start_4", "enemy", "hp_pct", 0.30, order=1,
         note="pending review fix v5")
    rule(conn, "rogue_6_start_4", "operator", "atk_pct", expr="region_count*0.10", order=2,
         note="pending review fix v5")
    rule(conn, "rogue_6_start_4", "operator", "hp_pct", expr="region_count*0.10", order=3,
         note="pending review fix v5")


def apply_pending_review_fixes(conn) -> None:
    """Handle all 118 pending relics (159 rules) from release-rule-review.md audit.

    This is the VERSION=5 comprehensive review pass.  It runs after all
    earlier fix functions and is designed to be idempotent — re-running is
    safe and will not duplicate rules.
    """
    # Phase 1: Copy rules from approved twins (same name + same usage_text).
    twin_count = _apply_twin_copies(conn)
    print(f"[pending-review] Phase 1: copied approved twin rules for {twin_count} relics")

    # Phase 2: Category-specific fixes for the remaining pending relics.
    remaining_before = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM relic_effect_rules
            WHERE review_status <> 'approved' AND calculation_status = 'active'
            """
        )
    ).scalar()
    print(f"[pending-review] Phase 2: {remaining_before} rules still pending after twin copy")

    _fix_rogue1_curse_relics(conn)
    _fix_simple_permanent_stats(conn)
    _approve_series_relics(conn)
    _fix_stacking_relics(conn)
    _fix_hp_threshold_relics(conn)
    _fix_conditional_toggle_relics(conn)

    # Safety check: report any relics still pending after all fixes.
    remaining_after = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM relic_effect_rules
            WHERE review_status <> 'approved' AND calculation_status = 'active'
            """
        )
    ).scalar()
    if remaining_after:
        details = conn.execute(
            text(
                """
                SELECT DISTINCT rr.relic_id, r.name
                FROM relic_effect_rules rr
                JOIN relics r ON r.id = rr.relic_id
                WHERE rr.review_status <> 'approved' AND rr.calculation_status = 'active'
                ORDER BY rr.relic_id
                """
            )
        ).mappings().all()
        for d in details:
            print(f"  STILL PENDING: {d['relic_id']} ({d['name']})")
        print(f"[pending-review] WARNING: {remaining_after} rules still pending after all fixes!")
    else:
        print("[pending-review] All pending rules resolved. Ready for release build.")


def main() -> None:
    init_schema()
    with get_engine().begin() as conn:
        apply_standard_profession_rules(conn)
        apply_confirmed_fixes(conn)
        apply_conditional_fixes(conn)
        apply_hand_fixes(conn)
        apply_user_reported_fixes(conn)
        apply_rogue6_audit_fixes(conn)
        apply_pending_review_fixes(conn)
        counts = conn.execute(
            text(
                """
                SELECT calculation_status,review_status,COUNT(*) count
                FROM relic_effect_rules WHERE rule_version=:version
                GROUP BY calculation_status,review_status
                """
            ),
            {"version": VERSION},
        ).mappings().all()
    print(json.dumps({"rule_version": VERSION, "counts": [dict(x) for x in counts]}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
