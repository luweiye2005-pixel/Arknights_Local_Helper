import { Card, Space, Table, Typography } from "antd";
import type { PanelResult } from "../types/panel";

const { Paragraph, Text } = Typography;

type PanelResultCardProps = {
  result?: PanelResult;
};

function operatorRows(result?: PanelResult) {
  if (!result?.final_panel) return [];
  const base = result.base_panel || {};
  const final = result.final_panel;
  return [
    { key: "hp", name: "生命", base: Number(base.hp).toFixed(0), final: Number(final.hp).toFixed(0) },
    { key: "atk", name: "攻击", base: Number(base.atk).toFixed(1), final: Number(final.atk).toFixed(1) },
    { key: "def", name: "防御", base: Number(base.def).toFixed(0), final: Number(final.def).toFixed(0) },
    { key: "res", name: "法抗", base: Number(base.res).toFixed(1), final: Number(final.res).toFixed(1) },
    {
      key: "aspd",
      name: "攻速",
      base: Number(base.attack_speed).toFixed(1),
      final: Number(final.attack_speed).toFixed(1),
    },
    {
      key: "interval",
      name: "攻击间隔(s)",
      base: Number(base.attack_interval).toFixed(3),
      final: Number(final.attack_interval).toFixed(3),
    },
    {
      key: "dmg",
      name: "伤害加成",
      base: "—",
      final: `${((Number(final.damage_pct) || 0) * 100).toFixed(1)}%`,
    },
  ];
}

function enemyRows(result?: PanelResult) {
  if (!result?.enemy_final_panel) return [];
  const base = result.enemy_base_panel;
  const difficulty = result.enemy_diff_panel;
  const final = result.enemy_final_panel;
  const row = (key: string, name: string, field: string, digits: number) => ({
    key,
    name,
    base: base ? Number(base[field]).toFixed(digits) : "-",
    diff: difficulty ? Number(difficulty[field]).toFixed(digits) : "-",
    final: Number(final[field]).toFixed(digits),
  });
  return [
    row("hp", "生命", "hp", 0),
    row("atk", "攻击", "atk", 1),
    row("def", "防御", "def", 0),
    row("res", "法抗", "magic_resistance", 1),
    row("aspd", "攻速", "attack_speed", 1),
    { key: "dtype", name: "伤害类型", base: "-", diff: "-", final: final.damage_type || "-" },
  ];
}

function relicBonusText(result?: PanelResult) {
  const bonus = result?.bonus;
  if (!bonus) return "";
  return [
    bonus.atk_pct_from_relics
      ? `藏品攻击+${(Number(bonus.atk_pct_from_relics) * 100).toFixed(1)}%`
      : "",
    bonus.aspd_from_relics ? `藏品攻速+${Number(bonus.aspd_from_relics).toFixed(1)}` : "",
    bonus.atk_pct_from_conditions
      ? `条件攻击+${(Number(bonus.atk_pct_from_conditions) * 100).toFixed(1)}%`
      : "",
    bonus.aspd_from_conditions ? `条件攻速+${Number(bonus.aspd_from_conditions).toFixed(1)}` : "",
    bonus.apply_outer_buff && bonus.atk_pct_from_outer
      ? `局外攻击+${(Number(bonus.atk_pct_from_outer) * 100).toFixed(1)}%`
      : "",
    bonus.atk_pct_from_manual
      ? `手填攻击+${(Number(bonus.atk_pct_from_manual) * 100).toFixed(1)}%`
      : "",
    bonus.enemy_atk_pct_from_relics
      ? `敌人攻击${(Number(bonus.enemy_atk_pct_from_relics) * 100).toFixed(1)}%`
      : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

const contributionLabels: Record<string, string> = {
  atk_pct: "攻击百分比", atk_flat: "攻击定值", hp_pct: "生命百分比",
  def_pct: "防御百分比", aspd: "攻击速度", res_flat: "法抗定值", res_pct: "法抗百分比",
};

function contributionLines(result?: PanelResult) {
  const data = result?.relic_contributions;
  if (!data) return [];
  const lines: { key: string; title: string; formula: string }[] = [];
  for (const [side, groups] of [["干员", data.operator_panel], ["敌人", data.enemy_panel]] as const) {
    for (const [attr, group] of Object.entries(groups || {})) {
      if (!group.items?.length) continue;
      const parts = group.items.map((item) => `${item.display}（${item.name}${item.condition ? ` · ${item.condition}` : ""}）`);
      const total = attr.endsWith("_pct") ? `${group.total * 100 >= 0 ? "+" : ""}${(group.total * 100).toFixed(1)}%` : `${group.total >= 0 ? "+" : ""}${group.total.toFixed(1)}`;
      lines.push({ key: `${side}-${attr}`, title: `${side}藏品${contributionLabels[attr] || attr}加成`, formula: `${parts.join(" ")} = ${total}` });
    }
  }
  const scopeLabels: Record<string, string> = {
    all: "通用", PHYS: "物理", MAGIC: "法术", TRUE: "真实", ELEMENTAL: "元素",
  };
  for (const [scope, group] of Object.entries(data.damage_factors || {})) {
    if (!group.items?.length) continue;
    const parts = group.items.map((item) => `${item.display}（${item.name}${item.condition ? ` · ${item.condition}` : ""}）`);
    lines.push({ key: `damage-${scope}`, title: `最终${scopeLabels[scope] || scope}伤害藏品加成`, formula: `${parts.join(" ")} = ×${(group.product * 100).toFixed(1)}%` });
  }
  return lines;
}

export default function PanelResultCard({ result }: PanelResultCardProps) {
  const compareRows = operatorRows(result);
  const enemies = enemyRows(result);
  const bonusText = relicBonusText(result);
  const contributionDetails = contributionLines(result);

  return (
    <Card className="panel" title="计算结果">
      {!result && <Paragraph className="muted">配置后点击计算。</Paragraph>}
      {result && (
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          {result.hit_damage != null && (
            <Text strong style={{ fontSize: 18 }}>
              单次伤害：{Number(result.hit_damage).toFixed(1)}
            </Text>
          )}
          {!!(result.relics_applied?.length || bonusText) && (
            <Text type="secondary">
              {result.relics_applied?.length
                ? `已应用藏品：${result.relics_applied.map((relic) => relic.name || relic.id).join("、")}`
                : ""}
              {bonusText ? `（${bonusText}）` : ""}
            </Text>
          )}
          {!!contributionDetails.length && (
            <div>
              <Text strong>藏品加成明细</Text>
              {contributionDetails.map((line) => (
                <div key={line.key}>
                  <Text>{line.title}：</Text><Text type="secondary">{line.formula}</Text>
                </div>
              ))}
            </div>
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
                {result.config?.theme_id
                  ? ` · 等效难度Lv${result.config.equivalent_grade ?? 0}`
                  : ""}
              </Text>
              <Table
                size="small"
                pagination={false}
                dataSource={enemies}
                columns={[
                  { title: "属性", dataIndex: "name", width: 80 },
                  { title: "基础", dataIndex: "base", width: 90 },
                  { title: "难度修正", dataIndex: "diff", width: 90 },
                  { title: "最终", dataIndex: "final", width: 90 },
                ]}
              />
            </>
          )}
          <div>
            <Text strong>计算过程</Text>
            <div className="result-steps">
              {(result.steps || []).map((step: string, index: number) => (
                <div key={index}>{step}</div>
              ))}
            </div>
          </div>
        </Space>
      )}
    </Card>
  );
}
