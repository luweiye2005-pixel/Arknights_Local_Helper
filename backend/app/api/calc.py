"""面板计算 API。"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.combat.panel import calculate_panel

router = APIRouter()


class ManualBonus(BaseModel):
    atk_pct: float = 0
    hp_pct: float = 0
    def_pct: float = 0
    aspd: float = 0


class SkillManual(BaseModel):
    """技能参数（自动或手填）。"""

    atk_pct: float = 0  # 「攻击力+X%」如 1.8
    hp_pct: float = 0  # 「生命值+X%」
    def_pct: float = 0  # 「防御力+X%」
    aspd: float = 0  # 攻速变化
    res_flat: float = 0  # 法抗定值（如 +15）
    res_pct: float = 0  # 法抗百分比（如 0.8=+80%）
    atk_scale_to: List[float] = Field(default_factory=list)  # 「提升至」如 [125, 220]
    damage_scale_pct: float = 100  # 「造成攻击力X%」


class EnemyManual(BaseModel):
    # 敌人面板修正（定值 / 百分比，可负）
    hp_pct: float = 0
    hp_flat: float = 0
    atk_pct: float = 0
    atk_flat: float = 0
    def_pct: float = 0
    def_flat: float = 0
    res_pct: float = 0
    res_flat: float = 0
    # 伤害结算用
    flat_def_reduce: float = 0
    def_pct_reduce: float = 0
    ignore_def_pct: float = 0
    ignore_res: float = 0
    phys_damage_taken_pct: float = 0
    phys_damage_reduction: float = 0
    arts_damage_taken_pct: float = 0
    arts_damage_reduction: float = 0
    true_damage_taken_pct: float = 0


class PanelCalcRequest(BaseModel):
    operator_id: Optional[str] = None
    enemy_id: Optional[str] = None
    enemy_level: int = 0
    elite: int = 2
    level: int = 80
    favor_percent: int = 100
    potential: int = 0
    module_id: Optional[str] = None
    module_level: int = 3
    module_atk_flat: float = 0
    module_atk_pct: float = 0
    relic_ids: List[str] = Field(default_factory=list)
    relic_conditions: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    theme_id: Optional[str] = None
    equivalent_grade: int = 0
    apply_outer_buff: bool = True
    manual_bonus: ManualBonus = Field(default_factory=ManualBonus)
    skill_manual: SkillManual = Field(default_factory=SkillManual)
    enemy_manual: EnemyManual = Field(default_factory=EnemyManual)
    damage_type: str = "PHYS"


@router.post("/panel")
def panel_calc(body: PanelCalcRequest):
    try:
        payload = body.model_dump()
        return calculate_panel(payload)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"面板计算失败: {e}") from e
