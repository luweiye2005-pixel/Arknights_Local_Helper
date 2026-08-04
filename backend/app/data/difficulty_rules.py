"""集成战略难度描述到结构化数值修正的转换规则。"""
from __future__ import annotations

import re


def parse_rule_desc_mods(theme_id: str, grade: int, rule_desc: str) -> list[dict]:
    """从难度 ruleDesc 启发式抽取敌人数值修正。"""
    description = rule_desc or ""
    modifiers: list[dict] = []
    if not description:
        return modifiers

    def blank(match: re.Match[str]) -> str:
        return " " * (match.end() - match.start())

    def add(target: str, attr: str, value: float, note: str = "ruleDesc") -> None:
        modifiers.append(
            {
                "theme_id": theme_id,
                "equivalent_grade": grade,
                "target": target,
                "attr": attr,
                "value": value,
                "op": "mul",
                "note": note,
            }
        )

    # 情境性受伤修正不能当成常驻效果。
    description = re.sub(
        r"处于[^，。；\n]{0,24}中的敌人受到的?(?:物理与法术|物理和法术)?伤害降低\s*\d+(?:\.\d+)?\s*%",
        " ",
        description,
    )

    elite_pattern = r"(?:精英及领袖|精英和领袖|精英与领袖|精英|领袖|boss|Boss)"
    for match in list(
        re.finditer(
            rf"{elite_pattern}敌人受到的?(?:物理与法术|物理和法术)?伤害降低\s*(\d+(?:\.\d+)?)\s*%",
            description,
        )
    ):
        value = -float(match.group(1)) / 100.0
        for target in ("elite_enemy", "boss"):
            add(target, "damage_taken_phys_pct", value, "ruleDesc elite/boss")
            add(target, "damage_taken_arts_pct", value, "ruleDesc elite/boss")
        description = description[: match.start()] + blank(match) + description[match.end() :]

    for match in list(
        re.finditer(
            r"受到的?(?:物理与法术|物理和法术)?伤害降低\s*(\d+(?:\.\d+)?)\s*%",
            description,
        )
    ):
        value = -float(match.group(1)) / 100.0
        add("enemy", "damage_taken_phys_pct", value)
        add("enemy", "damage_taken_arts_pct", value)
        description = description[: match.start()] + blank(match) + description[match.end() :]

    elite_stats = (
        ("生命值", "hp_pct"),
        ("生命", "hp_pct"),
        ("攻击力", "atk_pct"),
        ("攻击", "atk_pct"),
        ("防御力", "def_pct"),
        ("防御", "def_pct"),
    )
    for attr_cn, attr in elite_stats:
        for match in list(
            re.finditer(
                rf"(?:精英及领袖|精英和领袖|精英与领袖)敌人的?{attr_cn}.{{0,6}}(?:提升|增加|\+)\s*(\d+(?:\.\d+)?)\s*%",
                description,
            )
        ):
            value = float(match.group(1)) / 100.0
            for target in ("elite_enemy", "boss"):
                add(target, attr, value, "ruleDesc elite/boss")
            description = description[: match.start()] + blank(match) + description[match.end() :]

    common_stats = (
        ("攻击力", "atk_pct"),
        ("生命", "hp_pct"),
        ("防御力", "def_pct"),
        ("防御", "def_pct"),
    )
    for attr_cn, attr in common_stats:
        for match in list(
            re.finditer(
                rf"(?<![精英领袖及和与])敌人.{{0,6}}{attr_cn}.{{0,6}}(?:提升|增加|\+)\s*(\d+(?:\.\d+)?)\s*%",
                description,
            )
        ):
            prefix = description[max(0, match.start() - 8) : match.start()]
            if any(word in prefix for word in ("精英", "领袖", "boss", "Boss")):
                continue
            add("enemy", attr, float(match.group(1)) / 100.0)

    return modifiers
