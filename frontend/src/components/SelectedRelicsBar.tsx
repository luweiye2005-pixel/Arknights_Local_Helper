import { useMemo, useState } from "react";
import { Button, InputNumber, Space, Switch, Tooltip, Typography } from "antd";
import type { RelicBrief, RelicConditionParam, RelicConditionSchema } from "../api/client";

const { Text } = Typography;

type Props = {
  value: string[];
  catalog: RelicBrief[];
  conditions: Record<string, RelicConditionSchema>;
  conditionValues: Record<string, Record<string, boolean | number>>;
  onChange: (ids: string[]) => void;
  onConditionChange: (relicId: string, paramId: string, val: boolean | number) => void;
  sharedGold?: number;
  onSharedGoldChange?: (n: number) => void;
  iconRev?: number;
};

export function schemaOf(
  id: string,
  catalogMap: Map<string, RelicBrief>,
  conditions: Record<string, RelicConditionSchema>,
) {
  const r = catalogMap.get(id);
  return conditions[id] || r?.condition_schema;
}

export function sortPriority(schema?: RelicConditionSchema) {
  const params = schema?.params || [];
  if (params.some((p) => p.type === "toggle")) return 0;
  if (params.some((p) => p.type === "number" && p.id !== "gold")) return 1;
  if (params.length) return 2;
  return 3;
}

export function effectTooltip(r?: RelicBrief, schema?: RelicConditionSchema) {
  const bits: string[] = [];
  if (r?.usage) bits.push(r.usage);
  if (r?.effects?.length) {
    bits.push(
      r.effects.map((e) => `${e.target || "op"} ${e.attr}:${e.value}`).join("；"),
    );
  }
  if (schema?.params?.length) {
    bits.push("条件：" + schema.params.map((p) => p.label || p.id).join(" / "));
  }
  return bits.filter(Boolean).join("\n") || schema?.name || r?.name || "";
}

export default function SelectedRelicsBar({
  value,
  catalog,
  conditions,
  conditionValues,
  onChange,
  onConditionChange,
  sharedGold = 0,
  onSharedGoldChange,
  iconRev = 1,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const byId = useMemo(() => new Map(catalog.map((r) => [r.id, r])), [catalog]);

  const hasGold = useMemo(
    () =>
      value.some((id) =>
        (schemaOf(id, byId, conditions)?.params || []).some((p) => p.id === "gold"),
      ),
    [value, byId, conditions],
  );

  const displayIds = useMemo(() => {
    return [...value].sort((a, b) => {
      const pa = sortPriority(schemaOf(a, byId, conditions));
      const pb = sortPriority(schemaOf(b, byId, conditions));
      if (pa !== pb) return pa - pb;
      return value.indexOf(a) - value.indexOf(b);
    });
  }, [value, byId, conditions]);

  if (!value.length) {
    return (
      <div className="selected-relics empty">
        <Text type="secondary">尚未选择藏品。在下方网格点击添加。</Text>
      </div>
    );
  }

  function renderParam(id: string, p: RelicConditionParam, vals: Record<string, boolean | number>) {
    if (p.id === "gold") return null;
    if (p.auto) {
      return <Text key={p.id} type="secondary">{p.label}（自动判断）</Text>;
    }
    const cur =
      vals[p.id] !== undefined
        ? vals[p.id]
        : (p.default as boolean | number | undefined) ?? (p.type === "toggle" ? false : 0);
    if (p.type === "toggle") {
      return (
        <span key={p.id} className="cond-control">
          <Switch
            size="small"
            checked={Boolean(cur)}
            onChange={(c) => onConditionChange(id, p.id, c)}
          />
          <Text type="secondary">{p.label}</Text>
        </span>
      );
    }
    return (
      <span key={p.id} className="cond-control">
        <Text type="secondary">{p.label}</Text>
        <InputNumber
          size="small"
          min={p.min ?? 0}
          max={p.max ?? 9999}
          value={Number(cur) || 0}
          onChange={(n) => onConditionChange(id, p.id, Number(n) || 0)}
        />
      </span>
    );
  }

  return (
    <div className="selected-relics">
      <div className="selected-relics-head">
        <Space size={4}>
          <Button
            size="small"
            type="text"
            className="collapse-btn"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? "▶" : "▼"}
          </Button>
          <Text strong>已选藏品（{value.length}）</Text>
        </Space>
        <Button size="small" onClick={() => onChange([])}>
          清空
        </Button>
      </div>
      {!collapsed && (
        <>
          {hasGold && (
            <div className="selected-relics-gold">
              <Text type="secondary">当前源石锭</Text>
              <InputNumber
                min={0}
                max={999}
                value={sharedGold}
                onChange={(n) => onSharedGoldChange?.(Number(n) || 0)}
              />
              <Text type="secondary">（投币玩具 / 骑士戒律 / 金酒之杯共用）</Text>
            </div>
          )}
          <div className="selected-relics-list">
            {displayIds.map((id) => {
          const r = byId.get(id);
          const schema = schemaOf(id, byId, conditions);
          const src = `${r?.icon_url || `/api/v1/assets/relic/${id}`}?v=${iconRev}`;
          const vals = conditionValues[id] || {};
          const tip = effectTooltip(r, schema) || id;
          return (
            <div key={id} className="selected-relic-row">
              <Tooltip title={<span style={{ whiteSpace: "pre-wrap" }}>{tip}</span>}>
                <img src={src} alt="" width={40} height={40} style={{ cursor: "help" }} />
              </Tooltip>
              <div className="selected-relic-body">
                <div className="selected-relic-title">
                  <Text>{r?.name || schema?.name || id}</Text>
                  <Button
                    type="link"
                    size="small"
                    danger
                    onClick={() => onChange(value.filter((x) => x !== id))}
                  >
                    移除
                  </Button>
                </div>
                {!!schema?.params?.length && (
                  <Space wrap size="middle">
                    {schema.params.map((p) => renderParam(id, p, vals))}
                  </Space>
                )}
              </div>
            </div>
          );
        })}
          </div>
        </>
      )}
    </div>
  );
}
