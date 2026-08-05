import { useState, useCallback, useRef, useEffect } from "react";
import { message } from "antd";
import {
  RelicBrief,
  RelicConditionSchema,
  listThemes,
  getThemeOuterBuff,
} from "../../api/client";
import { errorMessage } from "../../utils/errorMessage";
import type { OuterBuff } from "../../types/panel";

const DEFAULT_OUTER: OuterBuff = { enabled: true, atk_pct: 0, hp_pct: 0, def_pct: 0, aspd: 0 };

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
  const [outerBuff, setOuterBuff] = useState<OuterBuff>(DEFAULT_OUTER);
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

  // 切换主题时自动填入该主题的满级局外加成
  const loadOuterBuffMax = useCallback(async (themeId: string) => {
    try {
      const buff = await getThemeOuterBuff(themeId);
      if (buff) {
        setOuterBuff({
          enabled: true,
          atk_pct: Math.round((buff.atk_pct || 0) * 100),
          hp_pct: Math.round((buff.hp_pct || 0) * 100),
          def_pct: Math.round((buff.def_pct || 0) * 100),
          aspd: buff.aspd || 0,
        });
      }
    } catch {
      // 无局外加成数据，保持默认
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
    outerBuff, setOuterBuff,
    restoringTheme,
    loadThemes,
    loadOuterBuffMax,
    onCatalogChange,
  };
}
