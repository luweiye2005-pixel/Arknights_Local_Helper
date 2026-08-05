import { useEffect, useMemo, useRef, useState } from "react";
import { Input, Select, Space, Typography } from "antd";
import { RelicBrief, RelicConditionSchema, ThemeDifficulty, assetsStatus, desktopAssetUrl, listRelics, listThemeDifficulties } from "../api/client";
import { difficultyLabel, pickDefaultDifficulty } from "../utils/difficulty";

const { Text } = Typography;

type Props = {
  theme?: string;
  themes: { id: string; name: string; relic_count?: number }[];
  value: string[];
  onChange: (ids: string[]) => void;
  onThemeChange: (theme: string) => void;
  equivalentGrade: number;
  onEquivalentGradeChange: (grade: number) => void;
  onCatalogChange?: (
    items: RelicBrief[],
    conditions: Record<string, RelicConditionSchema>,
  ) => void;
};

export default function RelicGrid({
  theme,
  themes,
  value,
  onChange,
  onThemeChange,
  equivalentGrade,
  onEquivalentGradeChange,
  onCatalogChange,
}: Props) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<RelicBrief[]>([]);
  const [loading, setLoading] = useState(false);
  const [iconRev, setIconRev] = useState(0);
  const [difficulties, setDifficulties] = useState<ThemeDifficulty[]>([]);
  const [diffKey, setDiffKey] = useState<string>();
  const selected = useMemo(() => new Set(value), [value]);
  const reqId = useRef(0);
  const equivRef = useRef(equivalentGrade);
  equivRef.current = equivalentGrade;

  useEffect(() => {
    assetsStatus()
      .then((st) => {
        const rev = Number(st?.icons?.revision || 0);
        if (rev > 0) setIconRev(rev);
      })
      .catch(() => undefined);
  }, [theme]);

  useEffect(() => {
    if (!theme) {
      setDifficulties([]);
      setDiffKey(undefined);
      return;
    }
    listThemeDifficulties(theme)
      .then((list) => {
        const normalized = list.map((d) => ({
          ...d,
          key: d.key || `${d.mode_difficulty}:${d.grade}`,
        }));
        setDifficulties(normalized);
        // Only reset difficulty if the restored equivalentGrade doesn't match
        // any valid difficulty for this theme (e.g. after switching themes).
        const current = equivRef.current;
        const matching = normalized.find(
          (d) => d.equivalent_grade === current,
        );
        if (!matching) {
          const preferred = pickDefaultDifficulty(normalized);
          if (preferred) {
            setDiffKey(preferred.key);
            onEquivalentGradeChange(preferred.equivalent_grade);
          }
        } else {
          setDiffKey(matching.key);
        }
      })
      .catch(() => {
        setDifficulties([]);
        setDiffKey(undefined);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);

  useEffect(() => {
    if (!theme) {
      setItems([]);
      return;
    }
    const id = ++reqId.current;
    setLoading(true);
    listRelics(theme, q || undefined, 5000, equivalentGrade)
      .then((d) => {
        if (id === reqId.current) {
          setItems(d.items);
          onCatalogChange?.(d.items, d.conditions || {});
        }
      })
      .catch(() => {
        if (id === reqId.current) {
          setItems([]);
          onCatalogChange?.([], {});
        }
      })
      .finally(() => {
        if (id === reqId.current) setLoading(false);
      });
  }, [theme, q, equivalentGrade, onCatalogChange]);

  function toggle(id: string) {
    if (selected.has(id)) onChange(value.filter((x) => x !== id));
    else onChange([...value, id]);
  }

  function onDifficultySelect(key: string) {
    setDiffKey(key);
    const hit = difficulties.find((d) => d.key === key);
    if (hit) onEquivalentGradeChange(hit.equivalent_grade);
  }

  const themeCount = themes.find((t) => t.id === theme)?.relic_count;
  const diffOptions = difficulties.map((d) => ({
    value: d.key,
    label: difficultyLabel(d),
  }));

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="middle">
      <Space wrap style={{ width: "100%" }}>
        <Select
          style={{ minWidth: 220 }}
          value={theme}
          onChange={onThemeChange}
          options={themes.map((t) => ({
            value: t.id,
            label: `${t.name || t.id}${t.relic_count != null ? ` (${t.relic_count})` : ""}`,
          }))}
        />
        <Select
          style={{ minWidth: 260 }}
          value={diffKey}
          onChange={onDifficultySelect}
          options={diffOptions.length ? diffOptions : [{ value: "NORMAL:0", label: "常规 · 难度0" }]}
          placeholder="选择难度"
          showSearch
          optionFilterProp="label"
        />
        <Input.Search
          allowClear
          placeholder="搜索藏品名称 / 效果"
          style={{ width: 260 }}
          onSearch={setQ}
          onChange={(e) => {
            if (!e.target.value) setQ("");
          }}
        />
        <Text type="secondary">
          已选 {value.length} · 展示 {items.length}
          {themeCount != null ? ` / ${themeCount}` : ""}
          {loading ? " · 加载中" : ""}
        </Text>
      </Space>

      <div className="relic-grid">
        {items.map((r) => {
          const active = selected.has(r.id);
          const src = desktopAssetUrl(`/api/v1/assets/relic/${r.id}?v=${iconRev || "1"}`);
          const tip = [
            r.usage || r.name,
            r.resolved_id && r.resolved_id !== r.id ? `难度升级→${r.resolved_name || r.resolved_id}` : "",
            (r.effects || []).map((e) => `${e.attr}:${e.value}`).join(", "),
          ]
            .filter(Boolean)
            .join("\n");
          return (
            <button
              type="button"
              key={r.id}
              className={`relic-card${active ? " active" : ""}`}
              title={tip}
              onClick={() => toggle(r.id)}
            >
              <img
                src={src}
                alt=""
                loading="lazy"
                decoding="async"
                width={56}
                height={56}
                onError={(e) => {
                  const el = e.target as HTMLImageElement;
                  el.onerror = null;
                  el.src =
                    "data:image/svg+xml," +
                    encodeURIComponent(
                      '<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56"><rect width="56" height="56" rx="6" fill="#1a2430"/></svg>',
                    );
                }}
              />
              <div className="relic-name">{r.name}</div>
            </button>
          );
        })}
      </div>
    </Space>
  );
}
