export type DamageType = "PHYS" | "MAGIC" | "TRUE" | "ELEMENTAL";

export type ManualBonus = {
  atk_pct: number;
  hp_pct: number;
  def_pct: number;
  aspd: number;
};

export type SkillManual = ManualBonus & {
  res_flat: number;
  res_pct: number;
  scale_to_1: number;
  scale_to_2: number;
  damage_scale_pct: number | null;
};

export type EnemyManual = {
  hp_pct: number;
  hp_flat: number;
  atk_pct: number;
  atk_flat: number;
  def_pct: number;
  def_flat: number;
  res_pct: number;
  res_flat: number;
  ignore_def_pct: number;
  ignore_res: number;
  phys_damage_taken_pct: number;
  phys_damage_reduction: number;
  arts_damage_taken_pct: number;
  arts_damage_reduction: number;
  true_damage_taken_pct: number;
  elemental_damage_taken_pct: number;
};

export type OperatorModuleLevel = {
  level: number;
  atk?: number;
  hp?: number;
  def?: number;
  defense?: number;
  atk_pct?: number;
  attack_speed?: number;
  trait_effects?: ModuleEffectCandidate[];
  talent_effects?: ModuleEffectCandidate[];
};

export type ModuleEffectCandidate = {
  talent_index?: number;
  name?: string;
  description?: string;
  potential_rank?: number;
};

export type OperatorModule = {
  id: string;
  name: string;
  type?: string;
  max_level?: number;
  levels?: OperatorModuleLevel[];
};

export type OperatorTalent = {
  index?: number;
  unlock_elite?: number;
  name?: string;
  potential_rank?: number;
  description?: string;
};

export type OperatorDetail = {
  id: string;
  name: string;
  rarity: number;
  profession?: string;
  profession_cn?: string;
  position?: string;
  sub_profession_cn?: string;
  phases?: { elite: number; max_level: number }[];
  modules?: OperatorModule[];
  talents?: OperatorTalent[];
};

export type CombatPanel = {
  hp?: number;
  atk?: number;
  def?: number;
  res?: number;
  magic_resistance?: number;
  attack_speed?: number;
  attack_interval?: number;
  damage_pct?: number;
  damage_type?: string;
  [key: string]: unknown;
};

export type PanelResult = {
  hit_damage?: number;
  operator?: { name?: string };
  enemy?: { name?: string; enemy_level?: string };
  module?: { name?: string; level?: number };
  config?: { theme_id?: string; equivalent_grade?: number };
  base_panel?: CombatPanel;
  final_panel?: CombatPanel;
  enemy_base_panel?: CombatPanel;
  enemy_diff_panel?: CombatPanel;
  enemy_final_panel?: CombatPanel;
  relics_applied?: { id?: string; name?: string }[];
  bonus?: Record<string, number | boolean | undefined>;
  relic_contributions?: {
    operator_panel?: Record<string, RelicContributionGroup>;
    enemy_panel?: Record<string, RelicContributionGroup>;
    conditional?: RelicContributionItem[];
    damage_factors?: Record<string, { product: number; formula?: string; items: RelicContributionItem[] }>;
  };
  steps?: string[];
};

export type RelicContributionItem = {
  relic_id: string;
  name: string;
  attr: string;
  value: number;
  display: string;
  factor?: number;
  condition?: string;
  formula?: string;
  rule_version?: number;
  source?: string;
};

export type RelicContributionGroup = {
  total: number;
  items: RelicContributionItem[];
};

export type PanelPersistedState = {
  operatorId?: string;
  enemyId?: string;
  theme?: string;
  equivalentGrade?: number;
  selectedRelics?: string[];
  relicConditions?: Record<string, Record<string, boolean | number>>;
  sharedGold?: number;
  applyOuterBuff?: boolean;
  manualBonus?: ManualBonus;
  skillManual?: SkillManual;
  enemyManual?: EnemyManual;
  damageType?: DamageType;
  moduleId?: string;
  moduleLevel?: number;
  selectedSkillId?: string;
  selectedSkillLevel?: number;
  elite?: number;
  level?: number;
  favor_percent?: number;
  potential?: number;
  result?: PanelResult;
};
