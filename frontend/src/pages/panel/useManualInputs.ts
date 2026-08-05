import { useState } from "react";
import type { ManualBonus, SkillManual, DamageType } from "../../types/panel";

export function useManualInputs() {
  const [manualBonus, setManualBonus] = useState<ManualBonus>({
    atk_pct: 0, hp_pct: 0, def_pct: 0, aspd: 0,
  });
  const [skillManual, setSkillManual] = useState<SkillManual>({
    atk_pct: 0, hp_pct: 0, def_pct: 0, aspd: 0,
    res_flat: 0, res_pct: 0,
    scale_to_1: 0, scale_to_2: 0,
    damage_scale_pct: null as number | null,
  });
  const [damageType, setDamageType] = useState<DamageType>("PHYS");

  return {
    manualBonus, setManualBonus,
    skillManual, setSkillManual,
    damageType, setDamageType,
  };
}
