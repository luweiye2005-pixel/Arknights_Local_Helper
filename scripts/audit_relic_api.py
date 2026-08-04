"""Audit every relic through the running FastAPI catalog and panel endpoints."""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000/api/v1"
REPORT_DATE = "20260804"
OPERATOR_ID = "char_002_amiya"
ENEMY_ID = "enemy_8010_mcnist"
SUPPORTED_OPERATOR = {
    "atk_pct", "atk_flat", "hp_pct", "def_pct", "aspd", "damage_pct",
    "phys_damage_pct", "arts_damage_pct", "ignore_def_pct", "true_damage",
}
SUPPORTED_ENEMY = {"hp_pct", "atk_pct", "def_pct", "aspd", "res_flat"}
COMBAT_WORDS = (
    "攻击力", "防御力", "生命值", "最大生命", "攻击速度", "攻速", "伤害",
    "法术抗性", "法抗", "无视防御", "敌人", "敌方单位",
)


def request_json(path: str, payload: dict | None = None, attempts: int = 3) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(Request(API + path, data=data, headers=headers), timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as caught:
            error = caught
            if attempt + 1 < attempts:
                time.sleep(0.2 * (attempt + 1))
    raise RuntimeError(str(error))


def condition_values(schema: dict, enabled: bool) -> dict:
    values = {}
    for param in schema.get("params") or []:
        pid = param.get("id")
        if not pid:
            continue
        if param.get("type") == "toggle":
            values[pid] = enabled
        elif enabled:
            values[pid] = param.get("max", param.get("default", 1))
        else:
            values[pid] = param.get("min", 0)
    return values


def calc_payload(relic_id: str, conditions: dict | None = None) -> dict:
    return {
        "operator_id": OPERATOR_ID, "enemy_id": ENEMY_ID, "enemy_level": 0,
        "elite": 2, "level": 80, "favor_percent": 100, "potential": 0,
        "relic_ids": [relic_id], "relic_conditions": conditions or {},
        "apply_outer_buff": False, "damage_type": "PHYS",
    }


def sign_satisfied(actual: float | bool, expected: float) -> bool:
    if expected > 0:
        return float(actual) > 0
    if expected < 0:
        return float(actual) < 0
    return True


def audit_one(item: dict, schemas: dict) -> dict:
    rid = item["id"]
    evidence = {"catalog": item}
    problems: list[str] = []
    try:
        detail = request_json(f"/relics/{quote(rid)}")
        evidence["detail"] = detail
        if not detail.get("id"):
            problems.append("详情 API 未返回藏品 id")
        if detail.get("calculation_status") == "ignored":
            return {"status": "catalog_only", "relic_id": rid, "name": detail.get("name"),
                    "theme": detail.get("theme"), "checked_effects": 0, "condition_checked": False,
                    "problems": problems, "evidence": evidence}

        schema = schemas.get(rid) or schemas.get(detail.get("id"))
        enabled_values = condition_values(schema, True) if schema else {}
        enabled_conditions = {rid: enabled_values} if schema else {}
        enabled = request_json("/calc/panel", calc_payload(rid, enabled_conditions))
        evidence["enabled_conditions"] = enabled_values
        evidence["enabled_result"] = {
            "modifiers": enabled.get("modifiers"), "bonus": enabled.get("bonus"),
            "relics_applied": enabled.get("relics_applied"),
            "final_panel": enabled.get("final_panel"),
            "enemy_final_panel": enabled.get("enemy_final_panel"),
            "hit_damage": enabled.get("hit_damage"),
        }
        applied = enabled.get("relics_applied") or []
        if not any(x.get("base_id") == rid for x in applied):
            problems.append("计算 API 未在 relics_applied 中记录该藏品")

        modifiers = enabled.get("modifiers") or {}
        bonus = enabled.get("bonus") or {}
        checked_effects = 0
        for effect in detail.get("effects") or item.get("effects") or []:
            target, attr = effect.get("target"), effect.get("attr")
            expected = float(effect.get("value") or 0)
            if target == "operator" and attr in SUPPORTED_OPERATOR:
                checked_effects += 1
                if not sign_satisfied(modifiers.get(attr, 0), expected):
                    problems.append(f"干员效果 {attr}={expected} 未反映到 modifiers（实际 {modifiers.get(attr, 0)}）")
            elif target == "enemy" and attr in SUPPORTED_ENEMY:
                checked_effects += 1
                actual = bonus.get(f"enemy_{attr}_from_relics", 0)
                if not sign_satisfied(actual, expected):
                    problems.append(f"敌人效果 {attr}={expected} 未反映到 bonus（实际 {actual}）")

        condition_checked = False
        if schema and schema.get("operator_effects"):
            relevant = {e.get("attr") for e in schema.get("operator_effects") or [] if e.get("attr")}
            condition_checked = True
            if schema.get("params"):
                disabled_values = condition_values(schema, False)
                disabled = request_json("/calc/panel", calc_payload(rid, {rid: disabled_values}))
                evidence["disabled_conditions"] = disabled_values
                evidence["disabled_result"] = {"modifiers": disabled.get("modifiers"), "final_panel": disabled.get("final_panel")}
                if relevant and not any(
                    (enabled.get("modifiers") or {}).get(attr) != (disabled.get("modifiers") or {}).get(attr)
                    for attr in relevant
                ):
                    problems.append(f"条件开启/关闭未改变声明字段：{sorted(relevant)}")
            else:
                for effect in schema.get("operator_effects") or []:
                    attr, expected = effect.get("attr"), float(effect.get("value") or 0)
                    if attr in SUPPORTED_OPERATOR and not sign_satisfied(modifiers.get(attr, 0), expected):
                        problems.append(f"无参数 schema 效果 {attr}={expected} 未生效（实际 {modifiers.get(attr, 0)}）")

        has_combat_text = any(word in (str(detail.get("usage") or "")) for word in COMBAT_WORDS)
        catalog_only = checked_effects == 0 and not condition_checked
        if catalog_only and has_combat_text and detail.get("calculation_status") != "ignored":
            return {"status": "suspected", "relic_id": rid, "name": detail.get("name"), "theme": detail.get("theme"),
                    "problems": ["描述包含战斗数值，但 API 没有可验证的结构化效果或条件 schema。"], "evidence": evidence}
        return {"status": "failed" if problems else ("catalog_only" if catalog_only else "passed"),
                "relic_id": rid, "name": detail.get("name"), "theme": detail.get("theme"),
                "checked_effects": checked_effects, "condition_checked": condition_checked,
                "problems": problems, "evidence": evidence}
    except Exception as error:
        return {"status": "request_failed", "relic_id": rid, "name": item.get("name"),
                "theme": item.get("theme"), "problems": [str(error)], "evidence": evidence}


def main() -> None:
    catalog = request_json("/relics?limit=5000")
    if catalog.get("source") != "mysql":
        raise RuntimeError(f"unexpected catalog source: {catalog.get('source')}")
    items, schemas = catalog.get("items") or [], catalog.get("conditions") or {}
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    checkpoint = reports / f"relic_api_audit_{REPORT_DATE}.checkpoint.json"
    results = []
    if checkpoint.exists():
        try:
            results = json.loads(checkpoint.read_text(encoding="utf-8"))
            results = [row for row in results if row.get("status") != "request_failed"]
        except (json.JSONDecodeError, OSError):
            results = []
    elif os.environ.get("RELIC_AUDIT_RETRY_ERRORS") == "1":
        previous = reports / f"relic_api_audit_{REPORT_DATE}.json"
        if previous.exists():
            old_results = json.loads(previous.read_text(encoding="utf-8")).get("results") or []
            results = [row for row in old_results if row.get("status") not in {"failed", "request_failed"}]
    completed = {row.get("relic_id") for row in results}
    pending = [item for item in items if item.get("id") not in completed]
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(audit_one, item, schemas) for item in pending]
        for future in as_completed(futures):
            results.append(future.result())
            if len(results) % 50 == 0:
                checkpoint.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    results.sort(key=lambda x: (x.get("theme") or "", x.get("relic_id") or ""))
    counts = {status: sum(x["status"] == status for x in results) for status in
              ("passed", "catalog_only", "suspected", "failed", "request_failed")}
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "api": API,
        "source": catalog.get("source"), "relic_count": len(items),
        "theme_count": len(catalog.get("themes") or []), "condition_schema_count": len(schemas),
        "counts": counts, "results": results,
    }
    json_path = reports / f"relic_api_audit_{REPORT_DATE}.json"
    md_path = reports / f"relic_api_audit_{REPORT_DATE}.md"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# 藏品真实 API 全量审计（{REPORT_DATE}）", "", "## 概况", "",
        f"- MySQL/API 藏品：{len(items)}", f"- 主题：{output['theme_count']}",
        f"- 条件 schema：{output['condition_schema_count']}",
        f"- 功能验证通过：{counts['passed']}", f"- 非战斗功能：{counts['catalog_only']}",
        f"- 疑似缺少结构化效果：{counts['suspected']}", f"- 功能失败：{counts['failed']}",
        f"- 请求失败：{counts['request_failed']}", "", "## 需要处理的项目", "",
    ]
    for row in results:
        if row["status"] not in {"suspected", "failed", "request_failed"}:
            continue
        lines += [f"### {row.get('name') or row['relic_id']}（{row['relic_id']}）", "",
                  f"- 分类：{row['status']}", f"- 主题：{row.get('theme')}",
                  f"- 问题：{'；'.join(row.get('problems') or [])}",
                  f"- 描述：{row.get('evidence', {}).get('detail', {}).get('usage', '')}", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    checkpoint.unlink(missing_ok=True)
    print(json.dumps({"relics": len(items), **counts, "json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
