/** 干员各精英阶段等级上限（按星级）。 */
const LEVEL_CAPS: Record<number, readonly [number, number, number]> = {
  6: [50, 80, 90],
  5: [50, 70, 80],
  4: [45, 60, 70],
  3: [40, 55, 70],
  2: [30, 55, 55],
  1: [30, 30, 30],
};

export function maxEliteForOperator(phasesLength?: number, rarity?: number): number {
  const fromPhases = Math.max(0, (phasesLength || 1) - 1);
  if (rarity != null && rarity <= 1) return Math.min(fromPhases, 0);
  if (rarity != null && rarity <= 2) return Math.min(fromPhases, 1);
  return Math.min(fromPhases, 2);
}

export function maxLevelForElite(
  rarity: number | undefined,
  elite: number,
  phaseMaxLevel?: number,
): number {
  const caps = rarity ? LEVEL_CAPS[rarity] : undefined;
  const idx = Math.max(0, Math.min(2, Math.floor(elite || 0)));
  if (caps) return caps[idx];
  if (phaseMaxLevel && phaseMaxLevel > 0) return phaseMaxLevel;
  return 90;
}
