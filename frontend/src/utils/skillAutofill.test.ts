import { describe, expect, it } from "vitest";
import type { OperatorSkill } from "../api/client";
import { skillAutofill } from "./skillAutofill";

describe("skillAutofill", () => {
  it("keeps panel ATK and hit multipliers in separate fields", () => {
    const skills: OperatorSkill[] = [
      {
        skill_id: "s1",
        levels: [
          {
            level: 7,
            atk_pct: 2,
            atk_scale: 1.5,
            damage_scale: 1,
            secondary_scale: 0,
            duration: 20,
            attack_speed: 30,
            base_attack_time: 0,
            cnt: 1,
            hp_pct: 0,
            def_pct: 0,
            res_flat: 0,
            res_pct: 0,
          },
        ],
      },
    ];

    const result = skillAutofill(skills, "s1", 7);
    expect(result?.skill.atk_pct).toBe(200);
    expect(result?.skill.damage_scale_pct).toBe(150);
    expect(result?.skill.aspd).toBe(30);
  });

  it("maps enemy percentage effects to UI percentages", () => {
    const skills: OperatorSkill[] = [
      {
        skill_id: "debuff",
        levels: [
          {
            level: 1,
            atk_scale: 1,
            atk_pct: 0,
            damage_scale: 1,
            secondary_scale: 0,
            duration: 10,
            attack_speed: 0,
            base_attack_time: 0,
            cnt: 1,
            hp_pct: 0,
            def_pct: 0,
            res_flat: 0,
            res_pct: 0,
            enemy_effects: { def_pct: -0.6, res_pct: -0.3 },
          },
        ],
      },
    ];

    const result = skillAutofill(skills, "debuff", 1);
    expect(result?.enemy.def_pct).toBe(-60);
    expect(result?.enemy.res_pct).toBe(-30);
  });

  it("returns null for an unknown skill", () => {
    expect(skillAutofill([], "missing", 7)).toBeNull();
  });

  it("does not multiply an alternative secondary damage segment", () => {
    const skills: OperatorSkill[] = [{
      skill_id: "segments",
      levels: [{
        level: 7, atk_scale: 1, atk_pct: 0, damage_scale: 1,
        secondary_scale: 1.8, duration: 0, attack_speed: 0,
        base_attack_time: 0, cnt: 1, hp_pct: 0, def_pct: 0,
        res_flat: 0, res_pct: 0,
      }],
    }];
    const result = skillAutofill(skills, "segments", 7);
    expect(result?.skill.damage_scale_pct).toBeNull();
    expect(result?.skill.scale_to_1).toBe(0);
    expect(result?.skill.scale_to_2).toBe(0);
  });
});
