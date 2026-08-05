import { useState } from "react";
import { message } from "antd";
import { useSearcher } from "../../hooks/useSearcher";
import { searchEnemies } from "../../api/client";
import { errorMessage } from "../../utils/errorMessage";
import type { EnemyManual } from "../../types/panel";

const DEFAULT_ENEMY_MANUAL: EnemyManual = {
  hp_pct: 0, hp_flat: 0,
  atk_pct: 0, atk_flat: 0,
  def_pct: 0, def_flat: 0,
  res_pct: 0, res_flat: 0,
  ignore_def_pct: 0, ignore_res: 0,
  phys_damage_taken_pct: 0, phys_damage_reduction: 0,
  arts_damage_taken_pct: 0, arts_damage_reduction: 0,
  true_damage_taken_pct: 0, elemental_damage_taken_pct: 0,
};

export function useEnemySelect() {
  const [enemyId, setEnemyId] = useState<string>();
  const [enemyManual, setEnemyManual] = useState<EnemyManual>(DEFAULT_ENEMY_MANUAL);

  const enemySearch = useSearcher(async (q: string) => {
    try {
      const items = await searchEnemies(q, 50);
      return (items || []).map((en) => ({
        value: en.id,
        label: `${en.name} (${en.enemy_level || "?"})`,
      }));
    } catch (error) {
      message.error(errorMessage(error, "敌人搜索失败"));
      return [];
    }
  });

  return {
    enemyId, setEnemyId,
    enemyManual, setEnemyManual,
    enemySearch,
  };
}
