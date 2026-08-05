import { useState, useCallback, useRef, useEffect } from "react";
import { message } from "antd";
import {
  RelicBrief,
  RelicConditionSchema,
  listThemes,
  getThemeOuterBuff,
} from "../../api/client";
import { errorMessage } from "../../utils/errorMessage";

export function useThemeRelics() {
  const [themes, setThemes] = useState<{ id: string; name: string; relic_count?: number }[]>([]);
  const [theme, setTheme] = useState<string>();
  const [equivalentGrade, setEquivalentGrade] = useState(0);
  const [selectedRelics, setSelectedRelics] = useState<string[]>([]);
  const [relicCatalog, setRelicCatalog] = useState<RelicBrief[]>([]);
  const [relicConditionsSchema, setRelicConditionsSchema] = useState<
    Record<string, RelicConditionSchema>
  >({});
  const [relicConditions, setRelicConditions] = useState<
    Record<string, Record<string, boolean | number>>
  >({});
  const [sharedGold, setSharedGold] = useState(0);
  const [applyOuterBuff, setApplyOuterBuff] = useState(true);
  const [outerBuffNote, setOuterBuffNote] = useState("");
  const restoringTheme = useRef(false);

  const loadThemes = useCallback(async () => {
    try {
      const t = await listThemes();
      setThemes(t);
      return t;
    } catch (e) {
      message.error(errorMessage(e as Error, "主题加载失败"));
      return [];
    }
  }, []);

  const loadOuterBuff = useCallback(async (themeId: string) => {
    try {
      const buff = await getThemeOuterBuff(themeId);
      if (buff) {
        const parts: string[] = [];
        const pctFields = ["atk_pct", "hp_pct", "def_pct", "aspd"] as const;
        for (const f of pctFields) {
          const v = Number(buff[f] ?? 0);
          if (v) parts.push(`${f === "aspd" ? "攻速" : f.replace("_pct", "").toUpperCase()}${v >= 0 ? "+" : ""}${(v * 100).toFixed(0)}%`);
        }
        setOuterBuffNote(parts.join(" "));
      } else {
        setOuterBuffNote("");
      }
    } catch {
      setOuterBuffNote("");
    }
  }, []);

  const onCatalogChange = useCallback(
    (items: RelicBrief[], conditions: Record<string, RelicConditionSchema>) => {
      setRelicCatalog(items);
      setRelicConditionsSchema(conditions);
    },
    [],
  );

  // Sync auto-applies when theme/relics change
  const syncAutoApplies = useCallback(() => {
    let changed = false;
    const next = { ...relicConditions };
    for (const rel of relicCatalog) {
      const schema = relicConditionsSchema[rel.id];
      if (!schema?.params) continue;
      const current = next[rel.id] || {};
      for (const p of schema.params) {
        if (!p.auto || p.id in current) continue;
        changed = true;
        if (!next[rel.id]) next[rel.id] = {};
        next[rel.id] = { ...next[rel.id], [p.id]: p.default ?? (p.type === "toggle" ? false : 0) };
      }
    }
    if (changed) setRelicConditions(next);
  }, [relicCatalog, relicConditionsSchema, relicConditions]);

  // Sync sharedGold across gold-scaling relics
  const syncSharedGold = useCallback(
    (gold: number) => {
      let changed = false;
      const next = { ...relicConditions };
      for (const rel of relicCatalog) {
        const schema = relicConditionsSchema[rel.id];
        if (!schema?.params) continue;
        for (const p of schema.params) {
          if (p.id === "gold") {
            changed = true;
            if (!next[rel.id]) next[rel.id] = {};
            next[rel.id] = { ...next[rel.id], gold };
          }
        }
      }
      if (changed) setRelicConditions(next);
    },
    [relicCatalog, relicConditionsSchema],
  );

  useEffect(() => { syncAutoApplies(); }, [syncAutoApplies]);
  useEffect(() => { syncSharedGold(sharedGold); }, [sharedGold, syncSharedGold]);

  return {
    themes, setThemes,
    theme, setTheme,
    equivalentGrade, setEquivalentGrade,
    selectedRelics, setSelectedRelics,
    relicCatalog,
    relicConditionsSchema,
    relicConditions, setRelicConditions,
    sharedGold, setSharedGold,
    applyOuterBuff, setApplyOuterBuff,
    outerBuffNote,
    restoringTheme,
    loadThemes,
    loadOuterBuff,
    onCatalogChange,
  };
}
