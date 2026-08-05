"""藏品计算使用的修正量数据模型。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

@dataclass
class CombatModifiers:
    """可叠加的战斗修正。"""

    atk_pct: float = 0.0
    atk_flat: float = 0.0
    def_flat: float = 0.0
    damage_pct: float = 0.0
    aspd: float = 0.0
    ignore_def_pct: float = 0.0
    true_damage: bool = False
    phys_damage_pct: float = 0.0
    arts_damage_pct: float = 0.0
    hp_pct: float = 0.0
    def_pct: float = 0.0
    res_pct: float = 0.0
    res_flat: float = 0.0
    notes: list[str] = field(default_factory=list)

    def merge(self, other: "CombatModifiers") -> "CombatModifiers":
        return CombatModifiers(
            atk_pct=self.atk_pct + other.atk_pct,
            atk_flat=self.atk_flat + other.atk_flat,
            def_flat=self.def_flat + other.def_flat,
            damage_pct=self.damage_pct + other.damage_pct,
            aspd=self.aspd + other.aspd,
            ignore_def_pct=min(1.0, self.ignore_def_pct + other.ignore_def_pct),
            true_damage=self.true_damage or other.true_damage,
            phys_damage_pct=self.phys_damage_pct + other.phys_damage_pct,
            arts_damage_pct=self.arts_damage_pct + other.arts_damage_pct,
            hp_pct=self.hp_pct + other.hp_pct,
            def_pct=self.def_pct + other.def_pct,
            res_pct=self.res_pct + other.res_pct,
            res_flat=self.res_flat + other.res_flat,
            notes=self.notes + other.notes,
        )

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class EnemyStatModifiers:
    """藏品对敌人面板的数值修正。"""

    hp_pct: float = 0.0
    atk_pct: float = 0.0
    def_pct: float = 0.0
    aspd: float = 0.0
    res_flat: float = 0.0
    notes: list[str] = field(default_factory=list)

    def merge(self, other: "EnemyStatModifiers") -> "EnemyStatModifiers":
        return EnemyStatModifiers(
            hp_pct=self.hp_pct + other.hp_pct,
            atk_pct=self.atk_pct + other.atk_pct,
            def_pct=self.def_pct + other.def_pct,
            aspd=self.aspd + other.aspd,
            res_flat=self.res_flat + other.res_flat,
            notes=self.notes + other.notes,
        )

    def to_dict(self) -> dict:
        return asdict(self)

def _mod_has_values(mod: CombatModifiers) -> bool:
    return any(
        [
            abs(mod.atk_pct) > 1e-12,
            abs(mod.atk_flat) > 1e-12,
            abs(mod.def_flat) > 1e-12,
            abs(mod.damage_pct) > 1e-12,
            abs(mod.aspd) > 1e-12,
            abs(mod.ignore_def_pct) > 1e-12,
            mod.true_damage,
            abs(mod.phys_damage_pct) > 1e-12,
            abs(mod.arts_damage_pct) > 1e-12,
            abs(mod.hp_pct) > 1e-12,
            abs(mod.def_pct) > 1e-12,
            abs(mod.res_pct) > 1e-12,
            abs(mod.res_flat) > 1e-12,
        ]
    )


def _enemy_mod_has_values(mod: EnemyStatModifiers) -> bool:
    return any([mod.hp_pct, mod.atk_pct, mod.def_pct, mod.aspd, mod.res_flat])


