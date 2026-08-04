import type { OperatorSkill } from "../api/client";

export type SkillManualValues = {
  atk_pct: number;
  hp_pct: number;
  def_pct: number;
  aspd: number;
  res_flat: number;
  res_pct: number;
  scale_to_1: number;
  scale_to_2: number;
  damage_scale_pct: number | null;
};

export type EnemySkillValues = {
  hp_pct: number;
  hp_flat: number;
  atk_pct: number;
  atk_flat: number;
  def_pct: number;
  def_flat: number;
  res_pct: number;
  res_flat: number;
};

export function skillAutofill(
  skills: OperatorSkill[],
  skillId: string | undefined,
  skillLevel: number,
): { skill: SkillManualValues; enemy: EnemySkillValues } | null {
  const selected = skills.find((item) => item.skill_id === skillId);
  const level =
    selected?.levels.find((item) => item.level === skillLevel) ||
    selected?.levels[selected.levels.length - 1];
  if (!level) return null;

  const skill: SkillManualValues = {
    atk_pct: 0,
    hp_pct: 0,
    def_pct: 0,
    aspd: 0,
    res_flat: 0,
    res_pct: 0,
    scale_to_1: 0,
    scale_to_2: 0,
    damage_scale_pct: null,
  };
  const hitScale = level.atk_scale || 1;

  if (level.atk_pct && Math.abs(level.atk_pct) > 0.001) {
    skill.atk_pct = Math.round(level.atk_pct * 100);
  }
  if (hitScale > 0 && Math.abs(hitScale - 1) > 0.001) {
    skill.damage_scale_pct = Math.round(hitScale * 100);
  }
  // secondary_scale is an alternative/conditional damage segment, not an
  // always-on multiplier. Putting it into a multiplicative input exaggerates
  // damage, so alternative segments stay manual.
  if (
    level.damage_scale &&
    Math.abs(level.damage_scale - 1) > 0.01 &&
    Math.abs(level.damage_scale - hitScale) > 0.01 &&
    (!level.secondary_scale || Math.abs(level.damage_scale - level.secondary_scale) > 0.01)
  ) {
    skill.scale_to_1 = Math.round(level.damage_scale * 100);
  }
  if (level.attack_speed && Math.abs(level.attack_speed) > 0.1) {
    skill.aspd = Math.round(level.attack_speed);
  }
  if (level.hp_pct && Math.abs(level.hp_pct) > 0.001) {
    skill.hp_pct = Math.round(level.hp_pct * 100);
  }
  if (level.def_pct && Math.abs(level.def_pct) > 0.001) {
    skill.def_pct = Math.round(level.def_pct * 100);
  }
  if (level.res_flat && Math.abs(level.res_flat) >= 0.001) {
    skill.res_flat = Math.round(level.res_flat * 10) / 10;
  }
  if (level.res_pct && Math.abs(level.res_pct) > 0.001) {
    skill.res_pct = Math.round(level.res_pct * 100);
  }

  const effects = level.enemy_effects || {};
  const enemy: EnemySkillValues = {
    hp_pct: effects.hp_pct ? Math.round(effects.hp_pct * 100) : 0,
    hp_flat: effects.hp_flat || 0,
    atk_pct: effects.atk_pct ? Math.round(effects.atk_pct * 100) : 0,
    atk_flat: effects.atk_flat || 0,
    def_pct: effects.def_pct ? Math.round(effects.def_pct * 100) : 0,
    def_flat: effects.def_flat || 0,
    res_pct: effects.res_pct ? Math.round(effects.res_pct * 100) : 0,
    res_flat: effects.res_flat || 0,
  };
  return { skill, enemy };
}
