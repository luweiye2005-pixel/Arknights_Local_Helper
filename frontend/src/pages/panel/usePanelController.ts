import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Form, message } from "antd";
import {
  calcPanel,
  getOperator,
  getOperatorSkills,
} from "../../api/client";
import { maxEliteForOperator, maxLevelForElite } from "../../utils/operatorCaps";
import { skillAutofill } from "../../utils/skillAutofill";
import { errorMessage } from "../../utils/errorMessage";
import { usePanelPersistence } from "../../hooks/usePanelPersistence";
import { selectEffectiveTalents } from "../../utils/moduleEffects";
import { useOperatorSelect } from "./useOperatorSelect";
import { useEnemySelect } from "./useEnemySelect";
import { useThemeRelics } from "./useThemeRelics";
import { useManualInputs } from "./useManualInputs";
import type {
  PanelPersistedState,
  PanelResult,
} from "../../types/panel";

export function usePanelController() {
  // ── Sub-hooks ──
  const op = useOperatorSelect();
  const en = useEnemySelect();
  const tr = useThemeRelics();
  const mi = useManualInputs();

  // ── Local state ──
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PanelResult>();
  const resultRef = useRef<PanelResult | undefined>(result);
  resultRef.current = result;
  const [persistenceReady, setPersistenceReady] = useState(false);
  const [form] = Form.useForm();
  const eliteWatch = Form.useWatch("elite", form) ?? 0;
  const levelWatch = Form.useWatch("level", form) ?? 1;
  const potentialWatch = Form.useWatch("potential", form) ?? 0;

  // ── Derived values ──
  const maxElite = useMemo(
    () => maxEliteForOperator(op.operator?.phases?.length, op.operator?.rarity),
    [op.operator],
  );
  const maxLevel = useMemo(() => {
    const elite = Math.max(0, Math.min(maxElite, Number(eliteWatch) || 0));
    const phaseMax = op.operator?.phases?.[elite]?.max_level;
    return maxLevelForElite(op.operator?.rarity, elite, phaseMax);
  }, [op.operator, eliteWatch, maxElite]);

  const moduleOptions = useMemo(
    () =>
      (op.operator?.modules || []).map((m) => ({
        value: m.id,
        label: `${m.type || "模组"} · ${m.name}`,
        max_level: m.max_level || m.levels?.length || 1,
      })),
    [op.operator],
  );
  const selectedModule = useMemo(
    () => (op.operator?.modules || []).find((m) => m.id === op.moduleId),
    [op.operator, op.moduleId],
  );
  const selectedModuleLevel = selectedModule?.levels?.find(
    (level) => level.level === op.moduleLevel,
  );
  const currentTalents = useMemo(
    () =>
      selectEffectiveTalents(
        op.operator?.talents,
        Number(eliteWatch),
        Number(potentialWatch),
      ),
    [op.operator, eliteWatch, potentialWatch],
  );

  // ── Auto-clamp elite/level ──
  useEffect(() => {
    if (!op.operator) return;
    const elite = Math.max(0, Math.min(maxElite, Number(eliteWatch) || 0));
    if (elite !== Number(eliteWatch)) {
      form.setFieldValue("elite", elite);
      return;
    }
    if (Number(levelWatch) > maxLevel) {
      form.setFieldValue("level", maxLevel);
    }
  }, [op.operator, maxElite, maxLevel, eliteWatch, levelWatch, form]);

  // ── Helper: auto-apply condition matching ──
  function matchAppliesAuto(
    auto: { position?: string; profession?: string[]; sub_profession_cn_any?: string[] } | undefined,
    operator: NonNullable<typeof op.operator>,
  ): boolean {
    if (!auto || !operator) return true;
    if (auto.position) {
      if (String(operator.position || "").toUpperCase() !== String(auto.position).toUpperCase())
        return false;
    }
    if (auto.profession?.length) {
      const p = String(operator.profession || "");
      const pcn = String(operator.profession_cn || "");
      const ok = auto.profession.some(
        (a) =>
          a.toUpperCase() === p.toUpperCase() ||
          a === pcn ||
          (a === "术士" && pcn === "术师"),
      );
      if (!ok) return false;
    }
    if (auto.sub_profession_cn_any?.length) {
      const scn = String(operator.sub_profession_cn || "");
      if (!auto.sub_profession_cn_any.includes(scn)) return false;
    }
    return true;
  }

  function syncAutoApplies() {
    if (!op.operator) return;
    tr.setRelicConditions((prev) => {
      const next = { ...prev };
      for (const rid of tr.selectedRelics) {
        const schema = tr.relicConditionsSchema[rid];
        const autoParams = (schema?.params || []).filter((p) => p.auto);
        if (!autoParams.length) continue;
        const values = { ...(next[rid] || {}) };
        for (const param of autoParams) {
          if (param.auto) values[param.id] = matchAppliesAuto(param.auto, op.operator!);
        }
        next[rid] = values;
      }
      return next;
    });
  }

  function syncSharedGold(gold: number) {
    tr.setSharedGold(gold);
    tr.setRelicConditions((prev) => {
      const next = { ...prev };
      for (const rid of tr.selectedRelics) {
        const schema = tr.relicConditionsSchema[rid];
        if (!(schema?.params || []).some((p) => p.id === "gold")) continue;
        next[rid] = { ...(next[rid] || {}), gold };
      }
      return next;
    });
  }

  // ── Operator selection ──
  async function pickOperator(id: string) {
    op.setOperatorId(id);
    op.setSelectedSkillId(undefined);
    op.setSelectedSkillLevel(7);
    op.setOperatorSkills([]);
    try {
      const operator = await getOperator(id);
      op.setOperator(operator);
      const eliteCap = maxEliteForOperator(operator.phases?.length, operator.rarity);
      const levelCap = maxLevelForElite(
        operator.rarity, eliteCap, operator.phases?.[eliteCap]?.max_level,
      );
      const firstMod = (operator.modules || [])[0];
      op.setModuleId(firstMod?.id);
      op.setModuleLevel(firstMod?.max_level || 3);
      form.setFieldsValue({ elite: eliteCap, level: levelCap, favor_percent: 100, potential: 0 });
      syncAutoApplies();
      getOperatorSkills(id).then(op.setOperatorSkills).catch(() => op.setOperatorSkills([]));
    } catch (error: unknown) {
      message.error(errorMessage(error, "加载干员失败"));
    }
  }

  // ── Skill auto-fill ──
  useEffect(() => {
    if (!op.selectedSkillId || !op.operatorSkills.length) return;
    const autofill = skillAutofill(op.operatorSkills, op.selectedSkillId, op.selectedSkillLevel);
    if (!autofill) return;
    mi.setSkillManual((previous) => ({ ...previous, ...autofill.skill }));
    en.setEnemyManual((previous) => ({ ...previous, ...autofill.enemy }));
  }, [op.selectedSkillId, op.selectedSkillLevel, op.operatorSkills]);

  // ── Relic selection helpers ──
  function onSelectedRelicsChange(ids: string[]) {
    tr.setSelectedRelics(ids);
    syncSharedGold(tr.sharedGold);
    if (op.operator) syncAutoApplies();
  }

  function onConditionChange(relicId: string, paramId: string, val: boolean | number) {
    tr.setRelicConditions((prev) => ({
      ...prev,
      [relicId]: { ...(prev[relicId] || {}), [paramId]: val },
    }));
  }

  // ── Persistence ──
  function getPersistState(): PanelPersistedState {
    const formVals = form.getFieldsValue();
    return {
      operatorId: op.operatorId,
      enemyId: en.enemyId,
      theme: tr.theme,
      equivalentGrade: tr.equivalentGrade,
      selectedRelics: tr.selectedRelics,
      relicConditions: tr.relicConditions,
      sharedGold: tr.sharedGold,
      outerBuff: tr.outerBuff,
      manualBonus: mi.manualBonus,
      skillManual: mi.skillManual,
      enemyManual: en.enemyManual,
      damageType: mi.damageType,
      moduleId: op.moduleId,
      moduleLevel: op.moduleLevel,
      selectedSkillId: op.selectedSkillId,
      selectedSkillLevel: op.selectedSkillLevel,
      elite: formVals.elite,
      level: formVals.level,
      favor_percent: formVals.favor_percent,
      potential: formVals.potential,
      result: resultRef.current,
    };
  }

  const { load: loadPersistedState, save: savePersistedState } = usePanelPersistence(
    getPersistState,
    persistenceReady,
  );
  const doSave = useCallback(() => {
    void savePersistedState().catch(() => {});
  }, [savePersistedState]);

  // ── Initial load + restore ──
  useEffect(() => {
    op.opSearch.onSearch("");
    tr.loadThemes().then((t) => {
      loadPersistedState()
        .then(async (saved) => {
          if (saved?.theme && t.some((th) => th.id === saved.theme)) {
            tr.restoringTheme.current = true;
            tr.setTheme(saved.theme as string);
          } else if (t[0]) {
            tr.setTheme(t[0].id);
          }
          if (saved?.operatorId) {
            await pickOperator(saved.operatorId as string);
          }
          if (saved?.enemyId) en.setEnemyId(saved.enemyId as string);
          if (saved?.equivalentGrade != null) tr.setEquivalentGrade(saved.equivalentGrade as number);
          if (saved?.selectedRelics) tr.setSelectedRelics(saved.selectedRelics as string[]);
          if (saved?.relicConditions)
            tr.setRelicConditions(saved.relicConditions as Record<string, Record<string, boolean | number>>);
          if (saved?.sharedGold != null) tr.setSharedGold(saved.sharedGold as number);
          if (saved?.outerBuff) tr.setOuterBuff(saved.outerBuff);
          if (saved?.manualBonus) mi.setManualBonus(saved.manualBonus as typeof mi.manualBonus);
          if (saved?.skillManual) mi.setSkillManual(saved.skillManual as typeof mi.skillManual);
          if (saved?.enemyManual) en.setEnemyManual(saved.enemyManual as typeof en.enemyManual);
          if (saved?.damageType) mi.setDamageType(saved.damageType);
          if (saved?.result) setResult(saved.result as PanelResult);
          if (saved?.moduleId) op.setModuleId(saved.moduleId as string);
          if (saved?.moduleLevel != null) op.setModuleLevel(saved.moduleLevel as number);
          if (saved?.selectedSkillId) op.setSelectedSkillId(saved.selectedSkillId as string);
          if (saved?.selectedSkillLevel != null)
            op.setSelectedSkillLevel(saved.selectedSkillLevel as number);
          else op.setSelectedSkillLevel(7);
          if (saved?.elite != null || saved?.level != null || saved?.favor_percent != null || saved?.potential != null) {
            form.setFieldsValue({
              elite: saved?.elite ?? 2,
              level: saved?.level ?? 80,
              favor_percent: saved?.favor_percent ?? 100,
              potential: saved?.potential ?? 0,
            });
          }
        })
        .catch(() => { if (t[0]) tr.setTheme(t[0].id); })
        .finally(() => setPersistenceReady(true));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Theme change handler ──
  useEffect(() => {
    if (!tr.theme) return;
    if (tr.restoringTheme.current) {
      tr.restoringTheme.current = false;
    } else {
      en.setEnemyId(undefined);
      tr.setSelectedRelics([]);
      tr.setRelicConditions({});
    }
    en.enemySearch.onSearch("");
    tr.loadOuterBuffMax(tr.theme);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tr.theme]);

  // ── Calculate ──
  async function runCalc() {
    if (!op.operatorId && !en.enemyId) {
      message.warning("请选择干员或敌人");
      return;
    }
    const values = form.getFieldsValue();
    const elite = Math.max(0, Math.min(maxElite, Number(values.elite) || 0));
    const level = Math.max(1, Math.min(maxLevel, Number(values.level) || 1));
    setLoading(true);
    try {
      const scaleTo: number[] = [];
      if (mi.skillManual.scale_to_1 > 0) scaleTo.push(mi.skillManual.scale_to_1);
      if (mi.skillManual.scale_to_2 > 0) scaleTo.push(mi.skillManual.scale_to_2);
      const data = await calcPanel({
        operator_id: op.operatorId,
        enemy_id: en.enemyId,
        elite,
        level,
        favor_percent: values.favor_percent ?? 100,
        potential: values.potential ?? 0,
        module_id: op.operatorId ? op.moduleId : undefined,
        module_level: op.moduleLevel,
        relic_ids: tr.selectedRelics,
        relic_conditions: tr.relicConditions,
        theme_id: tr.theme,
        equivalent_grade: tr.equivalentGrade,
        outer_buff: {
          enabled: tr.outerBuff.enabled,
          atk_pct: tr.outerBuff.atk_pct / 100,
          hp_pct: tr.outerBuff.hp_pct / 100,
          def_pct: tr.outerBuff.def_pct / 100,
          aspd: tr.outerBuff.aspd,
        },
        damage_type: mi.damageType,
        manual_bonus: {
          atk_pct: (mi.manualBonus.atk_pct || 0) / 100,
          hp_pct: (mi.manualBonus.hp_pct || 0) / 100,
          def_pct: (mi.manualBonus.def_pct || 0) / 100,
          aspd: mi.manualBonus.aspd || 0,
        },
        skill_manual: {
          atk_pct: (mi.skillManual.atk_pct || 0) / 100,
          hp_pct: (mi.skillManual.hp_pct || 0) / 100,
          def_pct: (mi.skillManual.def_pct || 0) / 100,
          aspd: mi.skillManual.aspd || 0,
          res_flat: mi.skillManual.res_flat || 0,
          res_pct: (mi.skillManual.res_pct || 0) / 100,
          atk_scale_to: scaleTo,
          damage_scale_pct: mi.skillManual.damage_scale_pct ?? 100,
        },
        enemy_manual: {
          hp_pct: (en.enemyManual.hp_pct || 0) / 100,
          hp_flat: en.enemyManual.hp_flat || 0,
          atk_pct: (en.enemyManual.atk_pct || 0) / 100,
          atk_flat: en.enemyManual.atk_flat || 0,
          def_pct: (en.enemyManual.def_pct || 0) / 100,
          def_flat: en.enemyManual.def_flat || 0,
          res_pct: (en.enemyManual.res_pct || 0) / 100,
          res_flat: en.enemyManual.res_flat || 0,
          ignore_def_pct: (en.enemyManual.ignore_def_pct || 0) / 100,
          ignore_res: en.enemyManual.ignore_res || 0,
          phys_damage_taken_pct: (en.enemyManual.phys_damage_taken_pct || 0) / 100,
          phys_damage_reduction: (en.enemyManual.phys_damage_reduction || 0) / 100,
          arts_damage_taken_pct: (en.enemyManual.arts_damage_taken_pct || 0) / 100,
          arts_damage_reduction: (en.enemyManual.arts_damage_reduction || 0) / 100,
          true_damage_taken_pct: (en.enemyManual.true_damage_taken_pct || 0) / 100,
          elemental_damage_taken_pct: (en.enemyManual.elemental_damage_taken_pct || 0) / 100,
        },
      });
      setResult(data);
      resultRef.current = data;
      doSave();
    } catch (error: unknown) {
      message.error(errorMessage(error, "计算失败"));
    } finally {
      setLoading(false);
    }
  }

  // ── Public interface (must match PanelController type exactly) ──
  return {
    operatorId: op.operatorId,
    setOperatorId: op.setOperatorId,
    enemyId: en.enemyId,
    setEnemyId: en.setEnemyId,
    operator: op.operator,
    setOperator: op.setOperator,
    themes: tr.themes,
    theme: tr.theme,
    setTheme: tr.setTheme,
    equivalentGrade: tr.equivalentGrade,
    setEquivalentGrade: tr.setEquivalentGrade,
    selectedRelics: tr.selectedRelics,
    relicCatalog: tr.relicCatalog,
    relicConditionsSchema: tr.relicConditionsSchema,
    relicConditions: tr.relicConditions,
    sharedGold: tr.sharedGold,
    outerBuff: tr.outerBuff,
    setOuterBuff: tr.setOuterBuff,
    manualBonus: mi.manualBonus,
    setManualBonus: mi.setManualBonus,
    skillManual: mi.skillManual,
    setSkillManual: mi.setSkillManual,
    enemyManual: en.enemyManual,
    setEnemyManual: en.setEnemyManual,
    damageType: mi.damageType,
    setDamageType: mi.setDamageType,
    moduleId: op.moduleId,
    setModuleId: op.setModuleId,
    moduleLevel: op.moduleLevel,
    setModuleLevel: op.setModuleLevel,
    operatorSkills: op.operatorSkills,
    selectedSkillId: op.selectedSkillId,
    setSelectedSkillId: op.setSelectedSkillId,
    selectedSkillLevel: op.selectedSkillLevel,
    setSelectedSkillLevel: op.setSelectedSkillLevel,
    loading,
    result,
    form,
    eliteWatch,
    potentialWatch,
    maxElite,
    maxLevel,
    opSearch: op.opSearch,
    enemySearch: en.enemySearch,
    moduleOptions,
    selectedModule,
    selectedModuleLevel,
    currentTalents,
    onCatalogChange: tr.onCatalogChange,
    pickOperator,
    onSelectedRelicsChange,
    onConditionChange,
    syncSharedGold,
    runCalc,
    doSave,
  };
}

export type PanelController = ReturnType<typeof usePanelController>;
