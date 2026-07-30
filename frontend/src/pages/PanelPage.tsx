import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  Card,
  Col,
  Divider,
  Form,
  InputNumber,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Typography,
  message,
} from "antd";
import RelicGrid from "../components/RelicGrid";
import SelectedRelicsBar from "../components/SelectedRelicsBar";
import {
  RelicBrief,
  RelicConditionSchema,
  calcPanel,
  getOperator,
  getThemeOuterBuff,
  listThemes,
  searchEnemies,
  searchOperators,
} from "../api/client";
import { maxEliteForOperator, maxLevelForElite } from "../utils/operatorCaps";

const { Title, Paragraph, Text } = Typography;

function useSearcher(searchFn: (q: string) => Promise<{ value: string; label: string }[]>) {
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const [fetching, setFetching] = useState(false);
  const timer = useRef<number>();
  const seq = useRef(0);

  function onSearch(q: string) {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      const id = ++seq.current;
      setFetching(true);
      try {
        const opts = await searchFn(q);
        if (id === seq.current) setOptions(opts);
      } catch {
        if (id === seq.current) setOptions([]);
      } finally {
        if (id === seq.current) setFetching(false);
      }
    }, 200);
  }

  return { options, fetching, onSearch, setOptions };
}

export default function PanelPage() {
  const [operatorId, setOperatorId] = useState<string>();
  const [enemyId, setEnemyId] = useState<string>();
  const [operator, setOperator] = useState<any>();
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
  const [manualBonus, setManualBonus] = useState({
    atk_pct: 0,
    hp_pct: 0,
    def_pct: 0,
    aspd: 0,
  });
  const [skillManual, setSkillManual] = useState({
    atk_pct: 0,
    scale_to_1: 0,
    scale_to_2: 0,
    damage_scale_pct: 100,
  });
  const [enemyManual, setEnemyManual] = useState({
    ignore_def_pct: 0,
    phys_damage_taken_pct: 0,
    phys_damage_reduction: 0,
  });
  const [damageType, setDamageType] = useState<"PHYS" | "MAGIC" | "TRUE">("PHYS");
  const [moduleId, setModuleId] = useState<string>();
  const [moduleLevel, setModuleLevel] = useState(3);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>();
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
        if (t[0]) setTheme(t[0].id);
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
      (operator?.modules || []).map((m: any) => ({
        value: m.id,
        label: `${m.type || "模组"} · ${m.name}`,
        max_level: m.max_level || m.levels?.length || 1,
      })),
    [operator],
  );
  const selectedModule = useMemo(
    () => (operator?.modules || []).find((m: any) => m.id === moduleId),
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
    op: any,
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

  function syncAutoApplies(op: any, relicIds: string[], schemas: Record<string, RelicConditionSchema>) {
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
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e.message || "加载干员失败");
    }
  }

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
          atk_scale_to: scaleTo,
          damage_scale_pct: skillManual.damage_scale_pct || 100,
        },
        enemy_manual: {
          ignore_def_pct: (enemyManual.ignore_def_pct || 0) / 100,
          phys_damage_taken_pct: (enemyManual.phys_damage_taken_pct || 0) / 100,
          phys_damage_reduction: (enemyManual.phys_damage_reduction || 0) / 100,
        },
      });
      setResult(data);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e.message || "计算失败");
    } finally {
      setLoading(false);
    }
  }

  const compareRows = result?.final_panel
    ? [
        {
          key: "hp",
          name: "生命",
          base: Number(result.base_panel?.hp).toFixed(0),
          final: Number(result.final_panel?.hp).toFixed(0),
        },
        {
          key: "atk",
          name: "攻击",
          base: Number(result.base_panel?.atk).toFixed(1),
          final: Number(result.final_panel?.atk).toFixed(1),
        },
        {
          key: "def",
          name: "防御",
          base: Number(result.base_panel?.def).toFixed(0),
          final: Number(result.final_panel?.def).toFixed(0),
        },
        {
          key: "res",
          name: "法抗",
          base: Number(result.base_panel?.res).toFixed(1),
          final: Number(result.final_panel?.res).toFixed(1),
        },
        {
          key: "aspd",
          name: "攻速",
          base: Number(result.base_panel?.attack_speed).toFixed(1),
          final: Number(result.final_panel?.attack_speed).toFixed(1),
        },
        {
          key: "interval",
          name: "攻击间隔(s)",
          base: Number(result.base_panel?.attack_interval).toFixed(3),
          final: Number(result.final_panel?.attack_interval).toFixed(3),
        },
        {
          key: "dmg",
          name: "伤害加成",
          base: "—",
          final: `${((Number(result.final_panel?.damage_pct) || 0) * 100).toFixed(1)}%`,
        },
      ]
    : [];

  const relicBonusText = result?.bonus
    ? [
        result.bonus.atk_pct_from_relics
          ? `藏品攻击+${(Number(result.bonus.atk_pct_from_relics) * 100).toFixed(1)}%`
          : "",
        result.bonus.aspd_from_relics ? `藏品攻速+${Number(result.bonus.aspd_from_relics).toFixed(1)}` : "",
        result.bonus.atk_pct_from_conditions
          ? `条件攻击+${(Number(result.bonus.atk_pct_from_conditions) * 100).toFixed(1)}%`
          : "",
        result.bonus.aspd_from_conditions
          ? `条件攻速+${Number(result.bonus.aspd_from_conditions).toFixed(1)}`
          : "",
        result.bonus.apply_outer_buff && result.bonus.atk_pct_from_outer
          ? `局外攻击+${(Number(result.bonus.atk_pct_from_outer) * 100).toFixed(1)}%`
          : "",
        result.bonus.atk_pct_from_manual
          ? `手填攻击+${(Number(result.bonus.atk_pct_from_manual) * 100).toFixed(1)}%`
          : "",
        result.bonus.enemy_atk_pct_from_relics
          ? `敌人攻击${(Number(result.bonus.enemy_atk_pct_from_relics) * 100).toFixed(1)}%`
          : "",
      ]
        .filter(Boolean)
        .join(" · ")
    : "";

  const enemyRows = result?.enemy_final_panel
    ? [
        { key: "hp", name: "生命", final: Number(result.enemy_final_panel.hp).toFixed(0) },
        { key: "atk", name: "攻击", final: Number(result.enemy_final_panel.atk).toFixed(1) },
        { key: "def", name: "防御", final: Number(result.enemy_final_panel.def).toFixed(0) },
        {
          key: "res",
          name: "法抗",
          final: Number(result.enemy_final_panel.magic_resistance).toFixed(1),
        },
        {
          key: "aspd",
          name: "攻速",
          final: Number(result.enemy_final_panel.attack_speed).toFixed(1),
        },
        {
          key: "dtype",
          name: "伤害类型",
          final: result.enemy_final_panel.damage_type || "-",
        },
      ]
    : [];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <div>
        <Title level={3} style={{ marginBottom: 4 }}>
          属性与藏品面板
        </Title>
        <Paragraph className="muted" style={{ marginBottom: 0 }}>
          可只算干员、只算敌人。选敌人时按实装物伤公式结算单次伤害；技能倍率需手填（攻击力+% / 提升至% / 造成%）。
        </Paragraph>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card className="panel" title="配置" bordered={false}>
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
                        const m = (operator?.modules || []).find((x: any) => x.id === v);
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

              <Divider>技能 / 伤害手填</Divider>
              <Paragraph type="secondary" style={{ marginBottom: 8 }}>
                「攻击力+X%」为直接乘算（与藏品ATK%加算）；多个「提升至」相乘。例：维什戴尔专三填攻击+180、提升至125与220。
              </Paragraph>
              <Row gutter={12}>
                <Col span={6}>
                  <Form.Item label="技能攻击力+%">
                    <InputNumber
                      style={{ width: "100%" }}
                      min={0}
                      value={skillManual.atk_pct}
                      onChange={(v) => setSkillManual((p) => ({ ...p, atk_pct: Number(v) || 0 }))}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="提升至%（天赋）">
                    <InputNumber
                      style={{ width: "100%" }}
                      min={0}
                      placeholder="如 125"
                      value={skillManual.scale_to_1 || undefined}
                      onChange={(v) => setSkillManual((p) => ({ ...p, scale_to_1: Number(v) || 0 }))}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="提升至%（技能）">
                    <InputNumber
                      style={{ width: "100%" }}
                      min={0}
                      placeholder="如 220"
                      value={skillManual.scale_to_2 || undefined}
                      onChange={(v) => setSkillManual((p) => ({ ...p, scale_to_2: Number(v) || 0 }))}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="造成攻击力%">
                    <InputNumber
                      style={{ width: "100%" }}
                      min={0}
                      value={skillManual.damage_scale_pct}
                      onChange={(v) =>
                        setSkillManual((p) => ({ ...p, damage_scale_pct: Number(v) || 100 }))
                      }
                    />
                  </Form.Item>
                </Col>
              </Row>
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
                <Col span={8}>
                  <Form.Item label="物理受伤加深%">
                    <InputNumber
                      style={{ width: "100%" }}
                      min={0}
                      value={enemyManual.phys_damage_taken_pct}
                      onChange={(v) =>
                        setEnemyManual((p) => ({ ...p, phys_damage_taken_pct: Number(v) || 0 }))
                      }
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item label="物理免伤%">
                    <InputNumber
                      style={{ width: "100%" }}
                      min={0}
                      max={100}
                      value={enemyManual.phys_damage_reduction}
                      onChange={(v) =>
                        setEnemyManual((p) => ({ ...p, phys_damage_reduction: Number(v) || 0 }))
                      }
                    />
                  </Form.Item>
                </Col>
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

              <Button type="primary" size="large" block loading={loading} onClick={runCalc} style={{ marginTop: 16 }}>
                计算面板 / 单次伤害
              </Button>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card className="panel" title="计算结果" bordered={false}>
            {!result && <Paragraph className="muted">配置后点击计算。</Paragraph>}
            {result && (
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                {result.hit_damage != null && (
                  <Text strong style={{ fontSize: 18 }}>
                    单次伤害：{Number(result.hit_damage).toFixed(1)}
                  </Text>
                )}
                {!!(result.relics_applied?.length || relicBonusText) && (
                  <Text type="secondary">
                    {result.relics_applied?.length
                      ? `已应用藏品：${(result.relics_applied || []).map((r: any) => r.name || r.id).join("、")}`
                      : ""}
                    {relicBonusText ? `（${relicBonusText}）` : ""}
                  </Text>
                )}
                {result.final_panel && (
                  <>
                    <Text>
                      干员：{result.operator?.name}
                      {result.module ? ` · 模组 ${result.module.name} Lv${result.module.level}` : ""}
                    </Text>
                    <Table
                      size="small"
                      pagination={false}
                      dataSource={compareRows}
                      columns={[
                        { title: "属性", dataIndex: "name" },
                        { title: "基础(含模组)", dataIndex: "base" },
                        { title: "战斗面板", dataIndex: "final" },
                      ]}
                    />
                  </>
                )}
                {result.enemy_final_panel && (
                  <>
                    <Text>
                      敌人：{result.enemy?.name}
                      {result.enemy?.enemy_level ? ` · ${result.enemy.enemy_level}` : ""}
                      （含难度/藏品）
                    </Text>
                    <Table
                      size="small"
                      pagination={false}
                      dataSource={enemyRows}
                      columns={[
                        { title: "属性", dataIndex: "name" },
                        { title: "计算后面板", dataIndex: "final" },
                      ]}
                    />
                  </>
                )}
                <div>
                  <Text strong>计算过程</Text>
                  <ol className="result-steps">
                    {(result.steps || []).map((s: string, i: number) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ol>
                </div>
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
