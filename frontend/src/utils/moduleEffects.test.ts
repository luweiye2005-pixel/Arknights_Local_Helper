import { describe, expect, it } from "vitest";
import { cleanGameText, selectEffectiveTalents, selectModuleEffects } from "./moduleEffects";

describe("module effect display selection", () => {
  it("selects the highest unlocked elite and potential talent candidate", () => {
    const talents = [
      { index: 0, unlock_elite: 1, potential_rank: 0, name: "E1" },
      { index: 0, unlock_elite: 2, potential_rank: 0, name: "E2" },
      { index: 0, unlock_elite: 2, potential_rank: 3, name: "E2P4" },
    ];
    expect(selectEffectiveTalents(talents, 2, 2)[0].name).toBe("E2");
    expect(selectEffectiveTalents(talents, 2, 3)[0].name).toBe("E2P4");
  });

  it("keeps distinct trait updates while selecting talent potential candidates", () => {
    const effects = [
      { description: "trait A", potential_rank: 0 },
      { description: "trait B", potential_rank: 0 },
      { talent_index: 1, description: "base", potential_rank: 0 },
      { talent_index: 1, description: "potential", potential_rank: 2 },
    ];
    expect(selectModuleEffects(effects, 0).map((x) => x.description)).toEqual(["trait A", "trait B", "base"]);
    const selected = selectModuleEffects(effects, 2);
    expect(selected[selected.length - 1]?.description).toBe("potential");
  });

  it("removes game rich-text tags", () => {
    expect(cleanGameText("<$ba.vup>攻击力+10%</>")).toBe("攻击力+10%");
  });
});
