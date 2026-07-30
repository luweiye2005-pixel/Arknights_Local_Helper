/** 集成战略难度选项工具。 */
export type ThemeDifficulty = {
  key: string;
  mode_difficulty: string;
  grade: number;
  equivalent_grade: number;
  name: string;
};

const MODE_CN: Record<string, string> = {
  NORMAL: "常规",
  EASY: "简单",
  CHALLENGE: "挑战",
  MONTH_TEAM: "月度",
};

export function difficultyLabel(d: ThemeDifficulty): string {
  const mode = MODE_CN[d.mode_difficulty] || d.mode_difficulty;
  if (d.mode_difficulty === "NORMAL") {
    return `${d.name || mode} · 难度${d.grade}`;
  }
  return `${d.name || mode} · ${mode}`;
}

export function difficultyKey(d: { mode_difficulty: string; grade: number }): string {
  return `${d.mode_difficulty}:${d.grade}`;
}

export function pickDefaultDifficulty(items: ThemeDifficulty[]): ThemeDifficulty | undefined {
  return (
    items.find((d) => d.mode_difficulty === "NORMAL" && d.grade === 0) ||
    items.find((d) => d.mode_difficulty === "NORMAL") ||
    items[0]
  );
}

/** 校验难度选项 value 唯一（避免 Ant Select 撞 key）。 */
export function assertUniqueDifficultyKeys(items: ThemeDifficulty[]): boolean {
  const keys = items.map((d) => d.key || difficultyKey(d));
  return keys.length === new Set(keys).size;
}
