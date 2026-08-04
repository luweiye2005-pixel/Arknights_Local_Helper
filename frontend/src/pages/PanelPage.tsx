import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Col,
  Divider,
  Form,
  InputNumber,
  Row,
  Select,
  Switch,
  Typography,
  message,
} from "antd";
import RelicGrid from "../components/RelicGrid";
import SelectedRelicsBar from "../components/SelectedRelicsBar";
import PanelResultCard from "../components/PanelResultCard";
import SkillManualSection from "../components/panel/SkillManualSection";
import EnemyStatsSection from "../components/panel/EnemyStatsSection";
import { useSearcher } from "../hooks/useSearcher";
import {
  RelicBrief,
  RelicConditionSchema,
  calcPanel,
  getOperator,
  getOperatorSkills,
  getThemeOuterBuff,
  listThemes,
  OperatorSkill,
  searchEnemies,
  searchOperators,
} from "../api/client";
import { maxEliteForOperator, maxLevelForElite } from "../utils/operatorCaps";
import { skillAutofill } from "../utils/skillAutofill";
import { errorMessage } from "../utils/errorMessage";
import { usePanelPersistence } from "../hooks/usePanelPersistence";
import type {
  DamageType,
  EnemyManual,
  ManualBonus,
  OperatorDetail,
  PanelPersistedState,
  PanelResult,
  SkillManual,
} from "../types/panel";

const { Title, Paragraph, Text } = Typography;

export default function PanelPage() {
  const [operatorId, setOperatorId] = useState<string>();
  const [enemyId, setEnemyId] = useState<string>();
  const [operator, setOperator] = useState<OperatorDetail>();
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
  const [manualBonus, setManualBonus] = useState<ManualBonus>({
    atk_pct: 0,
    hp_pct: 0,
    def_pct: 0,
    aspd: 0,
  });
  const [skillManual, setSkillManual] = useState<SkillManual>({
    atk_pct: 0,
    hp_pct: 0,
    def_pct: 0,
    aspd: 0,
    res_flat: 0,
    res_pct: 0,
    scale_to_1: 0,
    scale_to_2: 0,
    damage_scale_pct: null as number | null,
  });
  const [enemyManual, setEnemyManual] = useState<EnemyManual>({
    hp_pct: 0,
    hp_flat: 0,
    atk_pct: 0,
    atk_flat: 0,
    def_pct: 0,
    def_flat: 0,
    res_pct: 0,
    res_flat: 0,
    ignore_def_pct: 0,
    ignore_res: 0,
    phys_damage_taken_pct: 0,
    phys_damage_reduction: 0,
    arts_damage_taken_pct: 0,
    arts_damage_reduction: 0,
    true_damage_taken_pct: 0,
  });
  const [damageType, setDamageType] = useState<DamageType>("PHYS");
  const [moduleId, setModuleId] = useState<string>();
  const [moduleLevel, setModuleLevel] = useState(3);
  const [operatorSkills, setOperatorSkills] = useState<OperatorSkill[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState<string>();
  const [selectedSkillLevel, setSelectedSkillLevel] = useState(7);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PanelResult>();
  const [form] = Form.useForm();
  const eliteWatch = Form.useWatch("elite", form) ?? 0;
  const levelWatch = Form.useWatch("level", form) ?? 1;

  const maxElite = useMemo(
    () => maxEliteForOperator(operator?.phases?.length, operator?.rarity),
    [operator],
  );
  const maxLevel = useMemo(() => {
    const elite = Math.max(0, Math.min(maxElite, Number(eliteWatch) || 0));
    const phaseMax = operator?.phases?.[elite]?.max_level;
    return maxLevelForElite(operator?.rarity, elite, phaseMax);
  }, [operator, eliteWatch, maxElite]);

  const opSearch = useSearcher(async (q) => {
    const items = await searchOperators(q);
    return items.map((o) => ({
      value: o.id,
      label: `${o.name} · ${o.profession_cn || o.profession}${
        o.position_cn ? ` · ${o.position_cn}` : ""
      } · ${o.rarity}★`,
    }));
  });
  const enemySearch = useSearcher(async (q) => {
    const items = await searchEnemies(q, 50, theme);
    return items.map((e) => ({
      value: e.id,
      label: `${e.name}${e.enemy_level ? ` (${e.enemy_level})` : ""}`,
    }));
  });

  const onCatalogChange = useCallback(
    (items: RelicBrief[], conditions: Record<string, RelicConditionSchema>) => {
      setRelicCatalog(items);
      setRelicConditionsSchema(conditions);
    },
    [],
  );

  useEffect(() => {
    opSearch.onSearch("");
    listThemes()
      .then((t) => {
        setThemes(t);
        // 优先恢复保存的主题，否则选第一个
        loadPersistedState().then((saved) => {
          if (saved?.theme && t.some((th) => th.id === saved.theme)) {
            setTheme(saved.theme as string);
          } else if (t[0]) {
            setTheme(t[0].id);
          }
          // 恢复其他字段
          if (saved?.operatorId) {
            setOperatorId(saved.operatorId as string);
            pickOperator(saved.operatorId as string);
          }
          if (saved?.enemyId) setEnemyId(saved.enemyId as string);
          if (saved?.equivalentGrade != null) setEquivalentGrade(saved.equivalentGrade as number);
          if (saved?.selectedRelics) setSelectedRelics(saved.selectedRelics as string[]);
          if (saved?.relicConditions) setRelicConditions(saved.relicConditions as Record<string, Record<string, boolean | number>>);
          if (saved?.sharedGold != null) setSharedGold(saved.sharedGold as number);
          if (saved?.applyOuterBuff != null) setApplyOuterBuff(saved.applyOuterBuff as boolean);
          if (saved?.manualBonus) setManualBonus(saved.manualBonus as typeof manualBonus);
          if (saved?.skillManual) setSkillManual(saved.skillManual as typeof skillManual);
          if (saved?.enemyManual) setEnemyManual(saved.enemyManual as typeof enemyManual);
          if (saved?.damageType) setDamageType(saved.damageType as "PHYS" | "MAGIC" | "TRUE");
          if (saved?.moduleId) setModuleId(saved.moduleId as string);
          if (saved?.moduleLevel != null) setModuleLevel(saved.moduleLevel as number);
          if (saved?.selectedSkillId) setSelectedSkillId(saved.selectedSkillId as string);
          // 恢复技能等级，如果保存的值不在可用列表中则默认7
          if (saved?.selectedSkillLevel != null) setSelectedSkillLevel(saved.selectedSkillLevel as number);
          else setSelectedSkillLevel(7);
          if (saved?.elite != null || saved?.level != null || saved?.favor_percent != null || saved?.potential != null) {
            form.setFieldsValue({
              elite: saved.elite ?? 2,
              level: saved.level ?? 80,
              favor_percent: saved.favor_percent ?? 100,
              potential: saved.potential ?? 0,
            });
          }
        }).catch(() => {
          if (t[0]) setTheme(t[0].id);
        });
      })
      .catch((e) => message.error(e.message || "主题加载失败"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!theme) return;
    setEnemyId(undefined);
    setSelectedRelics([]);
    setRelicConditions({});
    enemySearch.onSearch("");
    getThemeOuterBuff(theme)
      .then((b) => {
        const bits = [
          b.atk_pct ? `攻击+${(b.atk_pct * 100).toFixed(0)}%` : "",
          b.hp_pct ? `生命+${(b.hp_pct * 100).toFixed(0)}%` : "",
          b.def_pct ? `防御+${(b.def_pct * 100).toFixed(0)}%` : "",
          b.aspd ? `攻速+${b.aspd}` : "",
        ].filter(Boolean);
        setOuterBuffNote(
          `${b.name || theme}${bits.length ? `：${bits.join(" · ")}` : "（无面板百分比）"}${
            b.note ? ` · ${b.note}` : ""
          }`,
        );
      })
      .catch(() => setOuterBuffNote(""));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);

  const moduleOptions = useMemo(
    () =>
      (operator?.modules || []).map((m) => ({
        value: m.id,
        label: `${m.type || "模组"} · ${m.name}`,
        max_level: m.max_level || m.levels?.length || 1,
      })),
    [operator],
  );
  const selectedModule = useMemo(
    () => (operator?.modules || []).find((m) => m.id === moduleId),
    [operator, moduleId],
  );

  useEffect(() => {
    if (!operator) return;
    const elite = Math.max(0, Math.min(maxElite, Number(eliteWatch) || 0));
    if (elite !== Number(eliteWatch)) {
      form.setFieldValue("elite", elite);
      return;
    }
    if (Number(levelWatch) > maxLevel) {
      form.setFieldValue("level", maxLevel);
    }
  }, [operator, maxElite, maxLevel, eliteWatch, levelWatch, form]);

  function matchAppliesAuto(
    auto: { position?: string; profession?: string[]; sub_profession_cn_any?: string[] } | undefined,
    op: OperatorDetail,
  ): boolean {
    if (!auto || !op) return true;
    if (auto.position) {
      if (String(op.position || "").toUpperCase() !== String(auto.position).toUpperCase()) {
        return false;
      }
    }
    if (auto.profession?.length) {
      const p = String(op.profession || "");
      const pcn = String(op.profession_cn || "");
      const ok = auto.profession.some(
        (a) => a.toUpperCase() === p.toUpperCase() || a === pcn || (a === "术士" && pcn === "术师"),
      );
      if (!ok) return false;
    }
    if (auto.sub_profession_cn_any?.length) {
      const scn = String(op.sub_profession_cn || "");
      if (!auto.sub_profession_cn_any.includes(scn)) return false;
    }
    return true;
  }

  function syncAutoApplies(op: OperatorDetail, relicIds: string[], schemas: Record<string, RelicConditionSchema>) {
    if (!op) return;
    setRelicConditions((prev) => {
      const next = { ...prev };
      for (const rid of relicIds) {
        const schema = schemas[rid];
        const appliesParam = schema?.params?.find((p) => p.id === "applies" && p.auto);
        if (!appliesParam?.auto) continue;
        next[rid] = {
          ...(next[rid] || {}),
          applies: matchAppliesAuto(appliesParam.auto, op),
        };
      }
      return next;
    });
  }

  function syncSharedGold(gold: number, relicIds: string[], schemas: Record<string, RelicConditionSchema>) {
    setSharedGold(gold);
    setRelicConditions((prev) => {
      const next = { ...prev };
      for (const rid of relicIds) {
        const schema = schemas[rid];
        if (!(schema?.params || []).some((p) => p.id === "gold")) continue;
        next[rid] = { ...(next[rid] || {}), gold };
      }
      return next;
    });
  }

  async function pickOperator(id: string) {
    setOperatorId(id);
    setSelectedSkillId(undefined);
    setSelectedSkillLevel(7);
    setOperatorSkills([]);
    try {
      const op = await getOperator(id);
      setOperator(op);
      const eliteCap = maxEliteForOperator(op.phases?.length, op.rarity);
      const levelCap = maxLevelForElite(op.rarity, eliteCap, op.phases?.[eliteCap]?.max_level);
      const firstMod = (op.modules || [])[0];
      setModuleId(firstMod?.id);
      setModuleLevel(firstMod?.max_level || 3);
      form.setFieldsValue({ elite: eliteCap, level: levelCap, favor_percent: 100, potential: 0 });
      syncAutoApplies(op, selectedRelics, relicConditionsSchema);
      // 加载技能列表
      getOperatorSkills(id).then(setOperatorSkills).catch(() => setOperatorSkills([]));
    } catch (error: unknown) {
      message.error(errorMessage(error, "加载干员失败"));
    }
  }

  // 选择技能后自动填充：atk → 面板攻击%；atk_scale → 造成攻击力%；二者不合并
  useEffect(() => {
    if (!selectedSkillId || !operatorSkills.length) return;
    const autofill = skillAutofill(operatorSkills, selectedSkillId, selectedSkillLevel);
    if (!autofill) return;
    setSkillManual((previous) => ({ ...previous, ...autofill.skill }));
    setEnemyManual((previous) => ({ ...previous, ...autofill.enemy }));
  }, [selectedSkillId, selectedSkillLevel, operatorSkills]);

  function onSelectedRelicsChange(ids: string[]) {
    setSelectedRelics(ids);
    syncSharedGold(sharedGold, ids, relicConditionsSchema);
    if (operator) syncAutoApplies(operator, ids, relicConditionsSchema);
  }

  function onConditionChange(relicId: string, paramId: string, val: boolean | number) {
    setRelicConditions((prev) => ({
      ...prev,
      [relicId]: { ...(prev[relicId] || {}), [paramId]: val },
    }));
  }

  function getPersistState(): PanelPersistedState {
    const formVals = form.getFieldsValue();
    return {
      operatorId,
      enemyId,
      theme,
      equivalentGrade,
      selectedRelics,
      relicConditions,
      sharedGold,
      applyOuterBuff,
      manualBonus,
      skillManual,
      enemyManual,
      damageType,
      moduleId,
      moduleLevel,
      selectedSkillId,
      selectedSkillLevel,
      elite: formVals.elite,
      level: formVals.level,
      favor_percent: formVals.favor_percent,
      potential: formVals.potential,
    };
  }

  const { load: loadPersistedState, save: savePersistedState } =
    usePanelPersistence(getPersistState);
  const doSave = useCallback(() => {
    void savePersistedState().catch(() => {});
  }, [savePersistedState]);

  async function runCalc() {
    if (!operatorId && !enemyId) {
      message.warning("请选择干员或敌人");
      return;
    }
    const values = form.getFieldsValue();
    const elite = Math.max(0, Math.min(maxElite, Number(values.elite) || 0));
    const level = Math.max(1, Math.min(maxLevel, Number(values.level) || 1));
    setLoading(true);
    try {
      const scaleTo: number[] = [];
      if (skillManual.scale_to_1 > 0) scaleTo.push(skillManual.scale_to_1);
      if (skillManual.scale_to_2 > 0) scaleTo.push(skillManual.scale_to_2);
      const data = await calcPanel({
        operator_id: operatorId,
        enemy_id: enemyId,
        elite,
        level,
        favor_percent: values.favor_percent ?? 100,
        potential: values.potential ?? 0,
        module_id: operatorId ? moduleId : undefined,
        module_level: moduleLevel,
        relic_ids: selectedRelics,
        relic_conditions: relicConditions,
        theme_id: theme,
        equivalent_grade: equivalentGrade,
        apply_outer_buff: applyOuterBuff,
        damage_type: damageType,
        manual_bonus: {
          atk_pct: (manualBonus.atk_pct || 0) / 100,
          hp_pct: (manualBonus.hp_pct || 0) / 100,
          def_pct: (manualBonus.def_pct || 0) / 100,
          aspd: manualBonus.aspd || 0,
        },
        skill_manual: {
          atk_pct: (skillManual.atk_pct || 0) / 100,
          hp_pct: (skillManual.hp_pct || 0) / 100,
          def_pct: (skillManual.def_pct || 0) / 100,
          aspd: skillManual.aspd || 0,
          res_flat: skillManual.res_flat || 0,
          res_pct: (skillManual.res_pct || 0) / 100,
          atk_scale_to: scaleTo,
          damage_scale_pct: skillManual.damage_scale_pct ?? 100,
        },
        enemy_manual: {
          hp_pct: (enemyManual.hp_pct || 0) / 100,
          hp_flat: enemyManual.hp_flat || 0,
          atk_pct: (enemyManual.atk_pct || 0) / 100,
          atk_flat: enemyManual.atk_flat || 0,
          def_pct: (enemyManual.def_pct || 0) / 100,
          def_flat: enemyManual.def_flat || 0,
          res_pct: (enemyManual.res_pct || 0) / 100,
          res_flat: enemyManual.res_flat || 0,
          ignore_def_pct: (enemyManual.ignore_def_pct || 0) / 100,
          ignore_res: enemyManual.ignore_res || 0,
          phys_damage_taken_pct: (enemyManual.phys_damage_taken_pct || 0) / 100,
          phys_damage_reduction: (enemyManual.phys_damage_reduction || 0) / 100,
          arts_damage_taken_pct: (enemyManual.arts_damage_taken_pct || 0) / 100,
          arts_damage_reduction: (enemyManual.arts_damage_reduction || 0) / 100,
          true_damage_taken_pct: (enemyManual.true_damage_taken_pct || 0) / 100,
        },
      });
      setResult(data);
      doSave();
    } catch (error: unknown) {
      message.error(errorMessage(error, "计算失败"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="panel-page">
        <div className="panel-page-left">
          <div>
            <Title level={3} style={{ marginBottom: 4 }}>
              属性与藏品面板
            </Title>
            <Paragraph className="muted" style={{ marginBottom: 8 }}>
              可只算干员、只算敌人。选敌人时按实装物伤公式结算单次伤害；技能倍率需手填（攻击力+% / 提升至% / 造成%）。
            </Paragraph>
          </div>

          <Card className="panel" title="配置">
            <Form form={form} layout="vertical" initialValues={{ elite: 2, level: 80, favor_percent: 100, potential: 0 }}>
              <Form.Item label="干员">
                <Select
                  showSearch
                  allowClear
                  placeholder="搜索干员，如：阿米娅（可选）"
                  filterOption={false}
                  options={opSearch.options}
                  loading={opSearch.fetching}
                  onSearch={opSearch.onSearch}
                  value={operatorId}
                  onChange={(v) => (v ? pickOperator(v) : (setOperatorId(undefined), setOperator(undefined)))}
                  notFoundContent={opSearch.fetching ? "搜索中…" : "无匹配"}
                />
              </Form.Item>

              <Row gutter={12}>
                <Col span={6}>
                  <Form.Item name="elite" label="精英">
                    <InputNumber min={0} max={maxElite} style={{ width: "100%" }} disabled={!operator} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item name="level" label={operator ? `等级(≤${maxLevel})` : "等级"}>
                    <InputNumber min={1} max={maxLevel} style={{ width: "100%" }} disabled={!operator} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item name="favor_percent" label="信赖%">
                    <InputNumber min={0} max={100} style={{ width: "100%" }} disabled={!operator} />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item name="potential" label="潜能">
                    <InputNumber min={0} max={5} style={{ width: "100%" }} disabled={!operator} />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={12}>
                <Col span={14}>
                  <Form.Item label="模组">
                    <Select
                      allowClear
                      placeholder={moduleOptions.length ? "选择模组" : "暂无模组"}
                      options={moduleOptions}
                      value={moduleId}
                      disabled={!operator}
                      onChange={(v) => {
                        setModuleId(v);
                        const m = (operator?.modules || []).find((x) => x.id === v);
                        setModuleLevel(m?.max_level || 3);
                      }}
                    />
                  </Form.Item>
                </Col>
                <Col span={10}>
                  <Form.Item label="模组等级">
                    <Select
                      value={moduleLevel}
                      disabled={!moduleId || !operator}
                      onChange={setModuleLevel}
                      options={Array.from(
                        { length: selectedModule?.max_level || selectedModule?.levels?.length || 3 },
                        (_, i) => ({ value: i + 1, label: `等级 ${i + 1}` }),
                      )}
                    />
                  </Form.Item>
                </Col>
              </Row>
              {selectedModule && (
                <Paragraph type="secondary" style={{ marginTop: -8, marginBottom: 8, fontSize: 13 }}>
                  模组效果：
                  {selectedModule.levels
                    ?.filter((l) => l.level === moduleLevel)
                    .map((l) => {
                      const parts = [];
                      if (l.atk) parts.push(`ATK+${l.atk}`);
                      if (l.atk_pct) parts.push(`ATK+${(l.atk_pct * 100).toFixed(0)}%`);
                      if (l.hp) parts.push(`HP+${l.hp}`);
                      if (l.defense) parts.push(`DEF+${l.defense}`);
                      if (l.attack_speed) parts.push(`攻速+${l.attack_speed}`);
                      return parts.join(" · ") || "无面板数值";
                    })}
                </Paragraph>
              )}
              {!!operator?.talents?.length && (
                <div style={{ marginBottom: 8, fontSize: 13, color: "var(--muted)" }}>
                  {operator.talents
                    .filter((t) => t.potential_rank === 0 && t.name)
                    .map((t, i: number) => (
                      <div key={i}>
                        天赋{i + 1}：{t.name}
                        {t.description ? ` — ${t.description}` : ""}
                      </div>
                    ))}
                </div>
              )}

              {operatorSkills.length > 0 && (
                <>
                  <Divider>技能（自动填充）</Divider>
                  <Row gutter={12}>
                    <Col span={14}>
                      <Form.Item label="技能选择">
                        <Select
                          allowClear
                          placeholder="选择技能自动填参数"
                          value={selectedSkillId}
                          onChange={(v) => setSelectedSkillId(v)}
                          options={operatorSkills.map((s) => ({
                            value: s.skill_id,
                            label: s.skill_name || s.skill_id,
                          }))}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={10}>
                      <Form.Item label="技能等级">
                        <Select
                          value={selectedSkillLevel}
                          onChange={setSelectedSkillLevel}
                          disabled={!selectedSkillId}
                          options={
                            selectedSkillId
                              ? (operatorSkills
                                  .find((s) => s.skill_id === selectedSkillId)
                                  ?.levels.map((l) => ({
                                    value: l.level,
                                    label: l.level === 10 ? "专三" : "Lv7",
                                  })) || [])
                              : []
                          }
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                </>
              )}
              <SkillManualSection value={skillManual} onChange={setSkillManual} />

              <Divider>局外与手填加成</Divider>
              <Form.Item
                label="满级局外加成"
                extra={outerBuffNote || "切换主题后加载补丁说明"}
              >
                <Switch checked={applyOuterBuff} onChange={setApplyOuterBuff} />
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  {applyOuterBuff ? "已启用（默认满级）" : "已关闭"}
                </Text>
              </Form.Item>
              <Row gutter={12}>
                <Col span={6}>
                  <Form.Item label="手填攻击%">
                    <InputNumber
                      style={{ width: "100%" }}
                      value={manualBonus.atk_pct}
                      onChange={(v) => setManualBonus((p) => ({ ...p, atk_pct: Number(v) || 0 }))}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="手填生命%">
                    <InputNumber
                      style={{ width: "100%" }}
                      value={manualBonus.hp_pct}
                      onChange={(v) => setManualBonus((p) => ({ ...p, hp_pct: Number(v) || 0 }))}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="手填防御%">
                    <InputNumber
                      style={{ width: "100%" }}
                      value={manualBonus.def_pct}
                      onChange={(v) => setManualBonus((p) => ({ ...p, def_pct: Number(v) || 0 }))}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="手填攻速">
                    <InputNumber
                      style={{ width: "100%" }}
                      value={manualBonus.aspd}
                      onChange={(v) => setManualBonus((p) => ({ ...p, aspd: Number(v) || 0 }))}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <EnemyStatsSection value={enemyManual} onChange={setEnemyManual} />

              <Divider>伤害结算</Divider>
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item label="伤害类型">
                    <Select
                      value={damageType}
                      onChange={setDamageType}
                      options={[
                        { value: "PHYS", label: "物理" },
                        { value: "MAGIC", label: "法术" },
                        { value: "TRUE", label: "真实" },
                      ]}
                    />
                  </Form.Item>
                </Col>
                {damageType === "PHYS" && (
                  <Col span={8}>
                    <Form.Item label="无视防御%">
                      <InputNumber
                        style={{ width: "100%" }}
                        min={0}
                        max={100}
                        value={enemyManual.ignore_def_pct}
                        onChange={(v) =>
                          setEnemyManual((p) => ({ ...p, ignore_def_pct: Number(v) || 0 }))
                        }
                      />
                    </Form.Item>
                  </Col>
                )}
                {damageType === "MAGIC" && (
                  <Col span={8}>
                    <Form.Item label="无视法抗">
                      <InputNumber
                        style={{ width: "100%" }}
                        min={0}
                        max={100}
                        value={enemyManual.ignore_res}
                        onChange={(v) =>
                          setEnemyManual((p) => ({ ...p, ignore_res: Number(v) || 0 }))
                        }
                      />
                    </Form.Item>
                  </Col>
                )}
                <Col span={8}>
                  <Form.Item
                    label={
                      damageType === "PHYS"
                        ? "物理受伤加深%"
                        : damageType === "MAGIC"
                          ? "法术受伤加深%"
                          : "真实受伤加深%"
                    }
                  >
                    <InputNumber
                      style={{ width: "100%" }}
                      value={
                        damageType === "PHYS"
                          ? enemyManual.phys_damage_taken_pct
                          : damageType === "MAGIC"
                            ? enemyManual.arts_damage_taken_pct
                            : enemyManual.true_damage_taken_pct
                      }
                      onChange={(v) => {
                        const val = Number(v) || 0;
                        setEnemyManual((p) => ({
                          ...p,
                          ...(damageType === "PHYS"
                            ? { phys_damage_taken_pct: val }
                            : damageType === "MAGIC"
                              ? { arts_damage_taken_pct: val }
                              : { true_damage_taken_pct: val }),
                        }));
                      }}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                {damageType === "PHYS" && (
                  <Col span={8}>
                    <Form.Item label="物理免伤%">
                      <InputNumber
                        style={{ width: "100%" }}
                        min={0}
                        max={100}
                        value={enemyManual.phys_damage_reduction}
                        onChange={(v) =>
                          setEnemyManual((p) => ({
                            ...p,
                            phys_damage_reduction: Number(v) || 0,
                          }))
                        }
                      />
                    </Form.Item>
                  </Col>
                )}
                {damageType === "MAGIC" && (
                  <Col span={8}>
                    <Form.Item label="法术免伤%">
                      <InputNumber
                        style={{ width: "100%" }}
                        min={0}
                        max={100}
                        value={enemyManual.arts_damage_reduction}
                        onChange={(v) =>
                          setEnemyManual((p) => ({
                            ...p,
                            arts_damage_reduction: Number(v) || 0,
                          }))
                        }
                      />
                    </Form.Item>
                  </Col>
                )}
              </Row>

              <Divider>敌人（当前主题）</Divider>
              <Form.Item label="敌人" extra={!theme ? "请先选择主题" : "列表仅含当前主题会出现的敌人"}>
                <Select
                  showSearch
                  allowClear
                  placeholder={theme ? "搜索当前主题敌人" : "请先选择主题"}
                  filterOption={false}
                  options={enemySearch.options}
                  loading={enemySearch.fetching}
                  onSearch={enemySearch.onSearch}
                  value={enemyId}
                  disabled={!theme}
                  onChange={(v) => setEnemyId(v || undefined)}
                  notFoundContent={
                    enemySearch.fetching ? "搜索中…" : "无匹配（若为空请到数据管理刷新主题敌人）"
                  }
                />
              </Form.Item>

              <Divider>集成战略藏品</Divider>
              <SelectedRelicsBar
                value={selectedRelics}
                catalog={relicCatalog}
                conditions={relicConditionsSchema}
                conditionValues={relicConditions}
                onChange={onSelectedRelicsChange}
                onConditionChange={onConditionChange}
                sharedGold={sharedGold}
                onSharedGoldChange={(n) => syncSharedGold(n, selectedRelics, relicConditionsSchema)}
              />
              <RelicGrid
                theme={theme}
                themes={themes}
                value={selectedRelics}
                onChange={onSelectedRelicsChange}
                onThemeChange={(t) => {
                  setTheme(t);
                }}
                equivalentGrade={equivalentGrade}
                onEquivalentGradeChange={setEquivalentGrade}
                onCatalogChange={onCatalogChange}
              />

              <Button type="primary" size="large" block loading={loading} onClick={runCalc} className="calc-inline-btn">
                计算面板 / 单次伤害
              </Button>
            </Form>
          </Card>
        </div>

        <div className="panel-page-right">
          <PanelResultCard result={result} />
        </div>
      </div>

      <Button
        className="calc-fab"
        type="primary"
        size="large"
        loading={loading}
        onClick={runCalc}
      >
        计算面板 / 单次伤害
      </Button>
      <Button
        className="save-fab"
        size="large"
        onClick={() => { doSave(); message.success("配置已保存到本地"); }}
      >
        保存配置
      </Button>
    </>
  );
}
