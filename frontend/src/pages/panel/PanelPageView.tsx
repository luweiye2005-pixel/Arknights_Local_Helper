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
import RelicGrid from "../../components/RelicGrid";
import SelectedRelicsBar from "../../components/SelectedRelicsBar";
import PanelResultCard from "../../components/PanelResultCard";
import SkillManualSection from "../../components/panel/SkillManualSection";
import EnemyStatsSection from "../../components/panel/EnemyStatsSection";
import { cleanGameText, selectModuleEffects } from "../../utils/moduleEffects";
import type { PanelController } from "./usePanelController";

const { Title, Paragraph, Text } = Typography;

type Props = {
  controller: PanelController;
};

export default function PanelPageView({ controller }: Props) {
  const {
    operatorId,
    setOperatorId,
    enemyId,
    setEnemyId,
    operator,
    setOperator,
    themes,
    theme,
    setTheme,
    equivalentGrade,
    setEquivalentGrade,
    selectedRelics,
    relicCatalog,
    relicConditionsSchema,
    relicConditions,
    sharedGold,
    applyOuterBuff,
    setApplyOuterBuff,
    outerBuffNote,
    manualBonus,
    setManualBonus,
    skillManual,
    setSkillManual,
    enemyManual,
    setEnemyManual,
    damageType,
    setDamageType,
    moduleId,
    setModuleId,
    moduleLevel,
    setModuleLevel,
    operatorSkills,
    selectedSkillId,
    setSelectedSkillId,
    selectedSkillLevel,
    setSelectedSkillLevel,
    loading,
    result,
    form,
    potentialWatch,
    maxElite,
    maxLevel,
    opSearch,
    enemySearch,
    moduleOptions,
    selectedModule,
    selectedModuleLevel,
    currentTalents,
    onCatalogChange,
    pickOperator,
    onSelectedRelicsChange,
    onConditionChange,
    syncSharedGold,
    runCalc,
    doSave,
  } = controller;

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
                <div style={{ marginTop: -8, marginBottom: 8, fontSize: 13, color: "var(--muted)" }}>
                  <div>模组面板：{selectedModuleLevel
                    ? (() => {
                      const l = selectedModuleLevel;
                      const parts = [];
                      if (l.atk) parts.push(`ATK+${l.atk}`);
                      if (l.atk_pct) parts.push(`ATK+${(l.atk_pct * 100).toFixed(0)}%`);
                      if (l.hp) parts.push(`HP+${l.hp}`);
                      if (l.defense) parts.push(`DEF+${l.defense}`);
                      if (l.attack_speed) parts.push(`攻速+${l.attack_speed}`);
                      return parts.join(" · ") || "无面板数值";
                    })()
                    : "无面板数值"}</div>
                  {selectModuleEffects(selectedModuleLevel?.trait_effects, Number(potentialWatch)).map((effect, i) => (
                    <div key={`trait-${i}`}>特性更新：{cleanGameText(effect.description)}</div>
                  ))}
                  {selectModuleEffects(selectedModuleLevel?.talent_effects, Number(potentialWatch)).map((effect, i) => (
                    <div key={`talent-${effect.talent_index ?? i}`}>
                      天赋升级{effect.name ? `「${effect.name}」` : ""}：{cleanGameText(effect.description)}
                    </div>
                  ))}
                </div>
              )}
              {!!currentTalents.length && (
                <div style={{ marginBottom: 8, fontSize: 13, color: "var(--muted)" }}>
                  {currentTalents.map((t, i: number) => (
                      <div key={i}>
                        当前天赋{i + 1}：{t.name}
                        {t.description ? ` — ${cleanGameText(t.description)}` : ""}
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
                        { value: "ELEMENTAL", label: "元素" },
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
                          : damageType === "TRUE"
                            ? "真实受伤加深%"
                            : "元素受伤加深%"
                    }
                  >
                    <InputNumber
                      style={{ width: "100%" }}
                      value={
                        damageType === "PHYS"
                          ? enemyManual.phys_damage_taken_pct
                          : damageType === "MAGIC"
                            ? enemyManual.arts_damage_taken_pct
                            : damageType === "TRUE"
                              ? enemyManual.true_damage_taken_pct
                              : enemyManual.elemental_damage_taken_pct
                      }
                      onChange={(v) => {
                        const val = Number(v) || 0;
                        setEnemyManual((p) => ({
                          ...p,
                          ...(damageType === "PHYS"
                            ? { phys_damage_taken_pct: val }
                            : damageType === "MAGIC"
                              ? { arts_damage_taken_pct: val }
                              : damageType === "TRUE"
                                ? { true_damage_taken_pct: val }
                                : { elemental_damage_taken_pct: val }),
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
                onSharedGoldChange={syncSharedGold}
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
    </>
  );
}
