import { describe, expect, it } from "vitest";
import { maxEliteForOperator, maxLevelForElite } from "./operatorCaps";
import {
  assertUniqueDifficultyKeys,
  difficultyKey,
  difficultyLabel,
  pickDefaultDifficulty,
} from "./difficulty";

describe("operatorCaps", () => {
  it("6星等级上限", () => {
    expect(maxLevelForElite(6, 0)).toBe(50);
    expect(maxLevelForElite(6, 1)).toBe(80);
    expect(maxLevelForElite(6, 2)).toBe(90);
  });

  it("5星等级上限", () => {
    expect(maxLevelForElite(5, 0)).toBe(50);
    expect(maxLevelForElite(5, 1)).toBe(70);
    expect(maxLevelForElite(5, 2)).toBe(80);
  });

  it("精英上限受稀有度限制", () => {
    expect(maxEliteForOperator(3, 6)).toBe(2);
    expect(maxEliteForOperator(3, 2)).toBe(1);
    expect(maxEliteForOperator(3, 1)).toBe(0);
  });
});

describe("difficulty utils", () => {
  const items = [
    { key: "EASY:0", mode_difficulty: "EASY", grade: 0, equivalent_grade: 0, name: "简单" },
    { key: "NORMAL:0", mode_difficulty: "NORMAL", grade: 0, equivalent_grade: 0, name: "正式调查" },
    { key: "NORMAL:3", mode_difficulty: "NORMAL", grade: 3, equivalent_grade: 3, name: "正式调查" },
    { key: "CHALLENGE:0", mode_difficulty: "CHALLENGE", grade: 0, equivalent_grade: 3, name: "挑战" },
  ];

  it("生成唯一 key", () => {
    expect(difficultyKey({ mode_difficulty: "NORMAL", grade: 0 })).toBe("NORMAL:0");
    expect(assertUniqueDifficultyKeys(items)).toBe(true);
  });

  it("撞 equivalent_grade 时 key 仍唯一", () => {
    const dupEq = [
      { key: "NORMAL:3", mode_difficulty: "NORMAL", grade: 3, equivalent_grade: 3, name: "N" },
      { key: "CHALLENGE:0", mode_difficulty: "CHALLENGE", grade: 0, equivalent_grade: 3, name: "C" },
    ];
    expect(assertUniqueDifficultyKeys(dupEq)).toBe(true);
    expect(new Set(dupEq.map((d) => d.equivalent_grade)).size).toBe(1);
  });

  it("默认选常规难度0", () => {
    const d = pickDefaultDifficulty(items);
    expect(d?.key).toBe("NORMAL:0");
  });

  it("标签区分常规档位", () => {
    expect(difficultyLabel(items[1])).toContain("难度0");
    expect(difficultyLabel(items[3])).toContain("挑战");
  });
});
