import type { ModuleEffectCandidate, OperatorTalent } from "../types/panel";

export function cleanGameText(value?: string): string {
  return (value || "").replace(/<[^>]*>/g, "").trim();
}

export function selectEffectiveTalents(
  talents: OperatorTalent[] = [],
  elite = 0,
  potential = 0,
): OperatorTalent[] {
  const groups = new Map<number, OperatorTalent[]>();
  talents.forEach((talent, fallbackIndex) => {
    const index = talent.index ?? fallbackIndex;
    groups.set(index, [...(groups.get(index) || []), talent]);
  });
  return [...groups.values()].flatMap((candidates) => {
    const eligible = candidates
      .filter((item) => (item.unlock_elite || 0) <= elite && (item.potential_rank || 0) <= potential)
      .sort((a, b) =>
        (a.unlock_elite || 0) - (b.unlock_elite || 0) ||
        (a.potential_rank || 0) - (b.potential_rank || 0),
      );
    return eligible.length ? [eligible[eligible.length - 1]] : [];
  });
}

export function selectModuleEffects(
  candidates: ModuleEffectCandidate[] = [],
  potential = 0,
): ModuleEffectCandidate[] {
  const groups = new Map<string, ModuleEffectCandidate[]>();
  candidates.forEach((candidate) => {
    const key = candidate.talent_index === undefined
      ? `trait:${candidate.description || ""}`
      : `talent:${candidate.talent_index}`;
    groups.set(key, [...(groups.get(key) || []), candidate]);
  });
  return [...groups.values()].flatMap((items) => {
    const eligible = items
      .filter((item) => (item.potential_rank || 0) <= potential)
      .sort((a, b) => (a.potential_rank || 0) - (b.potential_rank || 0));
    return eligible.length ? [eligible[eligible.length - 1]] : [];
  });
}
