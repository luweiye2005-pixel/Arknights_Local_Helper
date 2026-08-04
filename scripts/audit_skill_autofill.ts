// @ts-nocheck -- executed by vite-node; Node types are intentionally not a frontend dependency.
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { skillAutofill } from "../frontend/src/utils/skillAutofill";

const root = resolve(import.meta.dirname, "..");
const apiBase = process.env.SKILL_AUDIT_API || "http://127.0.0.1:8000/api/v1";
const stamp = process.env.SKILL_AUDIT_DATE || "20260804";
const reportDir = resolve(root, "reports");
const ZERO_ENEMY = { hp_pct: 0, hp_flat: 0, atk_pct: 0, atk_flat: 0, def_pct: 0, def_flat: 0, res_pct: 0, res_flat: 0 };

const source = JSON.parse(execFileSync(
  resolve(root, "backend/.venv/Scripts/python.exe"),
  [resolve(root, "scripts/export_skill_audit_source.py")],
  { cwd: resolve(root, "backend"), encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
));
const dbByKey = new Map(source.levels.map((x) => [`${x.operator_id}|${x.skill_id}|${x.level}`, x]));

async function getJson(url, attempts = 3) {
  let error;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (caught) {
      error = caught;
      if (attempt < attempts) await new Promise((done) => setTimeout(done, 250 * attempt));
    }
  }
  throw error;
}

function blackboardMap(raw) {
  const out = new Map();
  if (Array.isArray(raw)) for (const entry of raw) {
    if (entry && entry.key != null) out.set(String(entry.key).toLowerCase(), Number(entry.value));
  }
  else if (raw && typeof raw === "object") for (const [key, value] of Object.entries(raw)) out.set(key.toLowerCase(), Number(value));
  return out;
}

const fieldRules = {
  atk: ["skill", "atk_pct", 100], max_hp: ["skill", "hp_pct", 100], def: ["skill", "def_pct", 100],
  attack_speed: ["skill", "aspd", 1], magic_resistance: ["skill", "res_flat", 1],
  atk_scale: ["skill", "damage_scale_pct", 100], damage_scale: ["skill", "scale_to_1", 100],
};

function classify(db, autofill) {
  const description = db.description || "";
  const bb = blackboardMap(db.blackboard);
  const issues = [];
  const placeholders = [...description.matchAll(/\{\s*([\w.\[\]@-]+)\s*:\s*([^}]+)\}/g)];
  for (const match of placeholders) {
    const key = match[1].toLowerCase();
    const leafKey = key.split(/[@.\]]/).filter(Boolean).at(-1);
    const isNested = key !== leafKey;
    const rule = fieldRules[leafKey];
    if (!rule || !bb.has(key)) continue;
    if (leafKey === "atk_scale") {
      const selectedScaleKey = bb.has("attack@atk_scale") ? "attack@atk_scale" : "atk_scale";
      if (key !== selectedScaleKey) continue;
    }
    let [owner, configuredField, multiplier] = rule;
    let field = configuredField;
    let expected = Math.round(bb.get(key) * multiplier * 10) / 10;
    if ((leafKey === "atk_scale" || leafKey === "damage_scale") && Math.abs(expected - 100) < 0.11) continue;
    const nearbyText = description.slice(Math.max(0, (match.index || 0) - 90), match.index || 0);
    const targetContext = /(?:敌|目标|使其)[^。；\n]{0,70}$/.test(nearbyText);
    if (expected < 0 && targetContext && ["atk", "max_hp", "def"].includes(leafKey)) {
      owner = "enemy";
      field = { atk: "atk_pct", max_hp: "hp_pct", def: "def_pct" }[leafKey];
      if (!match[2].includes("%")) {
        expected = bb.get(key);
        field = { atk: "atk_flat", max_hp: "hp_flat", def: "def_flat" }[leafKey];
      }
    }
    if (leafKey === "magic_resistance" && match[2].includes("%")) {
      expected = Math.round(bb.get(key) * 1000) / 10;
      field = "res_pct";
    }
    // Nested positive values normally belong to summons or alternate attack
    // payloads. They must not be written into the selected operator panel.
    if (isNested && owner === "skill" && key !== "attack@atk_scale") continue;
    const actual = autofill[owner][field] ?? 0;
    if (Math.abs(actual - expected) > 0.11) issues.push(`描述占位符 ${key}=${expected}，但${owner === "skill" ? "技能" : "敌人"}.${field} 实填 ${actual}`);
  }
  if (issues.length) return { status: "confirmed", problems: issues, suggestion: "核对 blackboard 到 API 字段的解析或字段归属。" };
  return { status: "pass", problems: [], suggestion: "" };
}

const results = [];
const failures = [];
const noApiData = [];
let apiSkillCount = 0;
for (const operator of source.operators) {
  try {
    const payload = await getJson(`${apiBase}/operators/${encodeURIComponent(operator.id)}/skills`);
    if (payload.source !== "mysql") throw new Error(`source=${String(payload.source)}`);
    apiSkillCount += (payload.skills || []).length;
    if (!(payload.skills || []).length) noApiData.push({ operator_id: operator.id, operator_name: operator.name });
    for (const skill of payload.skills || []) for (const level of skill.levels || []) {
      const key = `${operator.id}|${skill.skill_id}|${level.level}`;
      const db = dbByKey.get(key);
      const autofill = skillAutofill([skill], skill.skill_id, level.level);
      if (!db || !autofill) {
        results.push({ operator_id: operator.id, operator_name: operator.name, skill_id: skill.skill_id, skill_name: skill.skill_name, level: level.level, status: "confirmed", review_status: "待审查", problems: [!db ? "API 等级在 MySQL 审计清单中不存在。" : "skillAutofill 返回 null。"], api_level: level, autofill });
        continue;
      }
      const verdict = classify(db, autofill);
      results.push({ operator_id: operator.id, operator_name: operator.name, skill_id: skill.skill_id, skill_name: skill.skill_name || db.name, skill_index: db.skill_index, level: level.level, max_level: db.max_level, description: db.description, blackboard: db.blackboard, db_parsed_effects: db.parsed_effects, api_level: level, autofill, ...verdict, review_status: verdict.status === "pass" ? null : "待审查" });
      dbByKey.delete(key);
    }
  } catch (error) {
    failures.push({ operator_id: operator.id, operator_name: operator.name, error: String(error?.message || error) });
  }
}
for (const db of dbByKey.values()) results.push({ ...db, status: "confirmed", review_status: "待审查", problems: ["MySQL 中存在目标等级，但真实 API 未返回。"], suggestion: "检查技能 API 的等级筛选和序列化。" });

const ulpian = results.find((x) => x.operator_id === "char_4145_ulpia" && x.skill_id === "skchr_ulpia_3" && x.level === 10);
const ulpianExpected = !!ulpian && ulpian.autofill?.skill.hp_pct === 80 && ulpian.autofill?.skill.atk_pct === 260 && ulpian.autofill?.skill.damage_scale_pct === 160 && JSON.stringify(ulpian.autofill.enemy) === JSON.stringify(ZERO_ENEMY);
if (ulpian && !ulpianExpected) {
  ulpian.status = "confirmed"; ulpian.review_status = "待审查";
  ulpian.problems = [...(ulpian.problems || []), "乌尔比安三技能基准不符：应为生命+80%、攻击+260%、伤害倍率160%，敌方修正全零。"];
}

const statusCounts = Object.fromEntries(["pass", "confirmed", "suspected", "unsupported"].map((s) => [s, results.filter((x) => x.status === s).length]));
const audit = { generated_at: new Date().toISOString(), api_base: apiBase, scope: "全部干员技能的 Lv7 与最高等级", database_counts: source.counts, api_operator_count: source.operators.length - failures.length, api_skill_count: apiSkillCount, no_api_data_operators: noApiData, audited_level_count: results.length, status_counts: statusCounts, request_failures: failures, ulpian_s3_check: { passed: ulpianExpected, actual: ulpian?.autofill || null }, results };

function block(value) { return "```json\n" + JSON.stringify(value, null, 2) + "\n```"; }
const md = [
  `# 全量技能自动填充审计（${stamp}）`, "", "## 审计概况", "",
  `- 环境：本地 MySQL、真实 FastAPI ${apiBase}、Vite/vite-node 复用前端 skillAutofill()`,
  `- 数据库：${source.counts.operators} 名干员，${source.counts.operator_skills} 个技能关系，${source.counts.operator_skill_levels} 个技能等级`,
  `- API：返回 ${apiSkillCount} 个技能；与 MySQL operator_skills ${apiSkillCount === source.counts.operator_skills ? "一致" : "不一致"}`,
  `- 审计：${results.length} 个 Lv7/最高等级；通过 ${statusCounts.pass}，确认错误 ${statusCounts.confirmed}，疑似 ${statusCounts.suspected}，不支持 ${statusCounts.unsupported}`,
  `- 无 API 技能数据干员：${noApiData.length}；API 请求失败干员：${failures.length}`, `- 乌尔比安三技能基准：${ulpianExpected ? "通过" : "未通过"}`, "",
  "## 问题清单", "",
];
for (const status of ["confirmed", "suspected", "unsupported"]) {
  const title = { confirmed: "确认错误", suspected: "疑似问题", unsupported: "当前模型不支持" }[status];
  const items = results.filter((x) => x.status === status);
  md.push(`### ${title}（${items.length}）`, "");
  if (!items.length) md.push("无。", "");
  for (const x of items) md.push(
    `#### ${x.operator_name || x.operator_id} / ${x.skill_name || x.skill_id} / Lv${x.level}`, "",
    `- 标识：\`${x.operator_id}\` / \`${x.skill_id}\``, `- 描述原文：${x.description || "（无）"}`,
    `- 问题：${(x.problems || []).join("；")}`, `- 建议方向：${x.suggestion || "人工核对。"}`, `- 状态：${x.review_status || "待审查"}`, "",
    "API 数据：", "", block(x.api_level || x.db_parsed_effects || null), "", "实际自动填充：", "", block(x.autofill || null), "",
  );
}
if (failures.length) md.push("### API 请求失败", "", block(failures), "");
if (noApiData.length) md.push("### 无 API 技能数据干员", "", block(noApiData), "");
md.push("## 说明", "", "本报告为只读审计结果。疑似问题未按确认错误处理；完整通过项及全部原始证据见同名 JSON。", "");
mkdirSync(reportDir, { recursive: true });
writeFileSync(resolve(reportDir, `skill_autofill_audit_${stamp}.json`), JSON.stringify(audit, null, 2), "utf8");
writeFileSync(resolve(reportDir, `skill_autofill_audit_${stamp}.md`), md.join("\n"), "utf8");
console.log(JSON.stringify({ reports: reportDir, audited: results.length, ...statusCounts, failures: failures.length, ulpian_s3: ulpianExpected }));
