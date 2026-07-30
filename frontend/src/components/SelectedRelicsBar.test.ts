import { describe, expect, it } from "vitest";
import type { RelicBrief, RelicConditionSchema } from "../api/client";
import { effectTooltip, schemaOf, sortPriority } from "./SelectedRelicsBar";

describe("schemaOf", () => {
  const catalogMap = new Map<string, RelicBrief>();
  catalogMap.set("r1", {
    id: "r1",
    name: "遗物1",
    theme: "rogue_1",
    usage: "攻击力+10%",
    condition_schema: {
      name: "内置条件",
      params: [{ id: "active", type: "toggle", label: "开启" }],
    },
  });
  catalogMap.set("r2", {
    id: "r2",
    name: "遗物2",
    theme: "rogue_1",
    usage: "防御力+10%",
  });

  const conditions: Record<string, RelicConditionSchema> = {
    r1: {
      name: "外部条件",
      params: [{ id: "active", type: "toggle", label: "外部" }],
    },
  };

  it("优先从 conditions 取 schema", () => {
    const s = schemaOf("r1", catalogMap, conditions);
    expect(s?.name).toBe("外部条件");
  });

  it("无 conditions 时回退到 relic.condition_schema", () => {
    const s = schemaOf("r2", catalogMap, {});
    // r2 has no condition_schema in catalog, so should be undefined
    expect(s).toBeUndefined();
  });

  it("不存在的 id 返回 undefined", () => {
    const s = schemaOf("r99", catalogMap, conditions);
    expect(s).toBeUndefined();
  });

  it("id 不在 catalogMap 中且不在 conditions 中返回 undefined", () => {
    const empty = new Map<string, RelicBrief>();
    const s = schemaOf("unknown", empty, {});
    expect(s).toBeUndefined();
  });
});

describe("sortPriority", () => {
  it("有 toggle 参数返回 0", () => {
    const s: RelicConditionSchema = {
      params: [
        { id: "active", type: "toggle", label: "开关" },
        { id: "gold", type: "number", label: "金币" },
      ],
    };
    expect(sortPriority(s)).toBe(0);
  });

  it("仅有非 gold 的 number 参数返回 1", () => {
    const s: RelicConditionSchema = {
      params: [{ id: "count", type: "number", label: "数量" }],
    };
    expect(sortPriority(s)).toBe(1);
  });

  it("仅有 gold 参数返回 2", () => {
    const s: RelicConditionSchema = {
      params: [{ id: "gold", type: "number", label: "金币" }],
    };
    expect(sortPriority(s)).toBe(2);
  });

  it("无参数返回 3", () => {
    const s: RelicConditionSchema = { params: [] };
    expect(sortPriority(s)).toBe(3);
  });

  it("undefined schema 返回 3", () => {
    expect(sortPriority(undefined)).toBe(3);
  });
});

describe("effectTooltip", () => {
  it("拼接 usage 文本", () => {
    const r: RelicBrief = {
      id: "r1",
      name: "A",
      theme: "rogue_1",
      usage: "攻击力+15%",
    };
    expect(effectTooltip(r)).toBe("攻击力+15%");
  });

  it("拼接 usage 和 effects", () => {
    const r: RelicBrief = {
      id: "r1",
      name: "A",
      theme: "rogue_1",
      usage: "攻击力+15%",
      effects: [{ attr: "atk_pct", value: 0.15, target: "operator" }],
    };
    const tip = effectTooltip(r);
    expect(tip).toContain("攻击力+15%");
    expect(tip).toContain("operator atk_pct:0.15");
  });

  it("拼接 schema params 标签", () => {
    const r: RelicBrief = {
      id: "r1",
      name: "A",
      theme: "rogue_1",
      usage: "效果文本",
    };
    const schema: RelicConditionSchema = {
      params: [
        { id: "gold", type: "number", label: "金币" },
        { id: "active", type: "toggle", label: "激活" },
      ],
    };
    const tip = effectTooltip(r, schema);
    expect(tip).toContain("效果文本");
    expect(tip).toContain("条件：金币 / 激活");
  });

  it("只有 schema name 时回退到 name", () => {
    const schema: RelicConditionSchema = {
      name: "条件藏品A",
      params: [],
    };
    expect(effectTooltip(undefined, schema)).toBe("条件藏品A");
  });

  it("r 和 schema 都有名时优先 schema.name（bits 为空时 fallback 顺序为 schema.name → r.name）", () => {
    const r: RelicBrief = {
      id: "r1",
      name: "遗物名",
      theme: "rogue_1",
      usage: "",
    };
    const schema: RelicConditionSchema = {
      name: "条件名",
      params: [],
    };
    // bits empty → fallback to schema.name (first in || chain)
    expect(effectTooltip(r, schema)).toBe("条件名");
  });

  it("只有 r.name 无 schema name 时回退到 r.name", () => {
    const r: RelicBrief = {
      id: "r1",
      name: "遗物名",
      theme: "rogue_1",
      usage: "",
    };
    const schema: RelicConditionSchema = { params: [] };
    expect(effectTooltip(r, schema)).toBe("遗物名");
  });

  it("全部为空时返回空字符串", () => {
    expect(effectTooltip(undefined, undefined)).toBe("");
  });

  it("只有 effects 没有 usage", () => {
    const r: RelicBrief = {
      id: "r1",
      name: "B",
      theme: "rogue_1",
      usage: "",
      effects: [
        { attr: "aspd", value: 10, target: "operator" },
        { attr: "hp_pct", value: 0.2, target: "operator" },
      ],
    };
    const tip = effectTooltip(r);
    expect(tip).toContain("operator aspd:10");
    expect(tip).toContain("operator hp_pct:0.2");
  });
});
