import axios from "axios";
import type { OperatorDetail, PanelPersistedState, PanelResult } from "../types/panel";

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
});

export const desktopToken = typeof window === "undefined"
  ? null
  : new URLSearchParams(window.location.search).get("token");
if (desktopToken) api.defaults.headers.common["X-Desktop-Token"] = desktopToken;

export function desktopAssetUrl(url: string): string {
  if (!desktopToken) return url;
  return `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(desktopToken)}`;
}

export type OperatorBrief = {
  id: string;
  name: string;
  rarity: number;
  profession: string;
  profession_cn: string;
  position?: string;
  position_cn?: string;
  sub_profession?: string;
};

export type EnemyBrief = {
  id: string;
  name: string;
  enemy_level?: string;
  description?: string;
};

export type RelicConditionParam = {
  id: string;
  type: "toggle" | "number";
  label: string;
  default?: boolean | number;
  min?: number;
  max?: number;
  auto?: {
    position?: string;
    profession?: string[];
    sub_profession_cn_any?: string[];
  };
};

export type RelicConditionSchema = {
  name?: string;
  params: RelicConditionParam[];
};

export type RelicBrief = {
  id: string;
  name: string;
  theme: string;
  usage: string;
  description?: string;
  icon_id?: string;
  icon_url?: string;
  resolved_id?: string;
  resolved_name?: string;
  effects?: { attr: string; value: number; target: string }[];
  condition_schema?: RelicConditionSchema;
};

export type OuterBuff = {
  name?: string;
  atk_pct?: number;
  hp_pct?: number;
  def_pct?: number;
  aspd?: number;
  note?: string;
};

export type ThemeDifficulty = {
  id?: number;
  key: string;
  theme_id: string;
  mode_difficulty: string;
  grade: number;
  equivalent_grade: number;
  name: string;
  score_factor?: number;
  rule_desc?: string;
};

export async function searchOperators(q: string, limit = 30) {
  const { data } = await api.get("/operators", { params: { q: q || undefined, limit } });
  return data.items as OperatorBrief[];
}

export async function getOperator(id: string) {
  const { data } = await api.get(`/operators/${id}`);
  return data as OperatorDetail;
}

export type EnemySkillEffects = {
  atk_pct?: number;
  atk_flat?: number;
  hp_pct?: number;
  hp_flat?: number;
  def_pct?: number;
  def_flat?: number;
  res_pct?: number;
  res_flat?: number;
};

export type OperatorSkill = {
  skill_id: string;
  skill_name?: string;
  levels: {
    level: number;
    name?: string;
    atk_scale: number;
    atk_pct: number;
    duration: number;
    description?: string;
    sp_cost?: number;
    sp_init?: number;
    attack_speed: number;
    base_attack_time: number;
    damage_scale: number;
    secondary_scale: number;
    cnt: number;
    hp_pct: number;
    def_pct: number;
    res_flat: number;
    res_pct: number;
    enemy_effects?: EnemySkillEffects;
  }[];
};

export async function getOperatorSkills(id: string) {
  const { data } = await api.get(`/operators/${id}/skills`);
  return data.skills as OperatorSkill[];
}

export async function searchEnemies(q: string, limit = 30, themeId?: string) {
  const { data } = await api.get("/enemies", {
    params: { q: q || undefined, limit, theme_id: themeId || undefined },
  });
  return data.items as EnemyBrief[];
}

export async function getEnemy(
  id: string,
  level = 0,
  themeId?: string,
  equivalentGrade?: number,
) {
  const { data } = await api.get(`/enemies/${id}`, {
    params: {
      level,
      theme_id: themeId || undefined,
      equivalent_grade: equivalentGrade ?? undefined,
    },
  });
  return data;
}

export async function listThemes() {
  const { data } = await api.get("/relics/themes");
  return data.themes as { id: string; name: string; relic_count?: number }[];
}

export async function listRelics(theme?: string, q?: string, limit = 5000, equivalentGrade?: number) {
  const { data } = await api.get("/relics", {
    params: { theme, q, limit, equivalent_grade: equivalentGrade },
  });
  return data as {
    themes: { id: string; name: string; relic_count?: number }[];
    items: RelicBrief[];
    conditions?: Record<string, RelicConditionSchema>;
  };
}

export async function listRelicConditions(theme?: string) {
  const { data } = await api.get("/relics/conditions", { params: { theme } });
  return data.items as Record<string, RelicConditionSchema>;
}

export async function getThemeOuterBuff(themeId: string) {
  const { data } = await api.get(`/relics/themes/${themeId}/outer-buff`);
  return data.buff as OuterBuff;
}

export async function listThemeDifficulties(themeId: string) {
  const { data } = await api.get(`/relics/themes/${themeId}/difficulties`);
  return data.items as ThemeDifficulty[];
}

export async function calcPanel(body: Record<string, unknown>): Promise<PanelResult> {
  const { data } = await api.post("/calc/panel", body);
  return data as PanelResult;
}

export async function knowledgeStatus() {
  const { data } = await api.get("/knowledge/status");
  return data;
}

export async function assetsStatus() {
  const { data } = await api.get("/assets/status");
  return data;
}

export async function reloadGamedata() {
  const { data } = await api.post("/knowledge/reload-gamedata");
  return data;
}

export async function syncGamedata() {
  const { data } = await api.post("/knowledge/sync-gamedata");
  return data;
}

export async function rebuildDb() {
  const { data } = await api.post("/knowledge/rebuild-db");
  return data;
}

export async function refreshThemeEnemies(downloadMissing = true) {
  const { data } = await api.post("/knowledge/refresh-theme-enemies", null, {
    params: { download_missing: downloadMissing },
    timeout: 1200000,
  });
  return data;
}

export async function prepareLocal(downloadIcons = true) {
  const { data } = await api.post("/knowledge/prepare-local", null, {
    params: { download_icons: downloadIcons },
  });
  return data;
}

export async function prefetchRelicIcons(all = true) {
  const { data } = await api.post("/assets/relics/prefetch", null, {
    params: { all, background: true },
  });
  return data;
}

export async function loadPanelState(): Promise<PanelPersistedState> {
  const { data } = await api.get("/knowledge/panel-state");
  return data || {};
}

export async function savePanelState(state: PanelPersistedState) {
  await api.post("/knowledge/panel-state", state);
}
