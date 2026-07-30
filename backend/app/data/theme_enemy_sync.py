"""集成战略主题敌人池：关卡 JSON 同步与解析。"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import httpx
from loguru import logger

from app.config import settings

MIRRORS = [
    "https://cdn.jsdelivr.net/gh/Kengxxiao/ArknightsGameData@master/{path}",
    "https://raw.gitmirror.com/Kengxxiao/ArknightsGameData/master/{path}",
    "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/{path}",
]


def level_id_to_rel_path(level_id: str) -> str | None:
    """Obt/Roguelike/RO1/level_rogue1_1-1
    -> zh_CN/gamedata/levels/obt/roguelike/ro1/level_rogue1_1-1.json

    Obt/Roguelike/RO4/LevelReplacers/level_rogue4_1-1_r1
    -> .../ro4/levelreplacers/level_rogue4_1-1_r1.json
    """
    if not level_id:
        return None
    parts = [p for p in level_id.replace("\\", "/").split("/") if p]
    if not parts:
        return None
    lower = [p.lower() for p in parts]
    try:
        roguelike_i = lower.index("roguelike")
    except ValueError:
        fname = parts[-1]
        if not fname.lower().endswith(".json"):
            fname = f"{fname}.json"
        m = re.search(r"level_rogue(\d+)", fname, re.I)
        if not m:
            return None
        return f"zh_CN/gamedata/levels/obt/roguelike/ro{m.group(1)}/{fname}"

    rest = [p.lower() for p in parts[roguelike_i + 1 :]]
    if not rest:
        return None
    if not rest[-1].endswith(".json"):
        rest[-1] = f"{rest[-1]}.json"
    return "zh_CN/gamedata/levels/obt/roguelike/" + "/".join(rest)


def local_level_path(rel: str) -> Path:
    # data/gamedata/levels/obt/roguelike/ro1/...
    # strip zh_CN/gamedata/ prefix when storing under gamedata_path
    suffix = rel
    for prefix in ("zh_CN/gamedata/", "zh_CN\\gamedata\\"):
        if suffix.startswith(prefix):
            suffix = suffix[len(prefix) :]
            break
    return settings.gamedata_path / suffix.replace("\\", "/")


def download_bytes(rel_path: str, timeout: float = 60.0) -> bytes:
    last_err: Exception | None = None
    # 路径大小写：优先小写，再试原始分段
    candidates = [rel_path]
    if rel_path != rel_path.lower():
        candidates.append(rel_path.lower())
    for path in candidates:
        for tmpl in MIRRORS:
            url = tmpl.format(path=path)
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    r = client.get(url)
                    r.raise_for_status()
                    return r.content
            except Exception as e:
                last_err = e
    raise RuntimeError(f"下载失败 {rel_path}: {last_err}")


def ensure_level_file(level_id: str, *, download: bool = True) -> Path | None:
    rel = level_id_to_rel_path(level_id)
    if not rel:
        return None
    dest = local_level_path(rel)
    if dest.exists() and dest.stat().st_size > 50:
        return dest
    if not download:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = download_bytes(rel)
    dest.write_bytes(data)
    return dest


def collect_theme_level_ids(detail: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for st in (detail.get("stages") or {}).values():
        if not isinstance(st, dict):
            continue
        lid = st.get("levelId")
        if lid:
            ids.add(str(lid))
        for r in st.get("levelReplaceIds") or []:
            if r:
                ids.add(str(r))
    return ids


def enemies_from_level_json(data: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for ref in data.get("enemyDbRefs") or []:
        if isinstance(ref, dict) and ref.get("id"):
            out.add(str(ref["id"]))
    for e in data.get("enemies") or []:
        if isinstance(e, str):
            out.add(e)
        elif isinstance(e, dict) and e.get("id"):
            out.add(str(e["id"]))
    return out


def extract_theme_enemy_ids(
    theme_id: str,
    detail: dict[str, Any],
    *,
    download_missing: bool = True,
    max_workers: int = 8,
) -> set[str]:
    """从 gameConst + 关卡 JSON 收集主题敌人 ID。"""
    enemy_ids: set[str] = set()
    gc = detail.get("gameConst") or {}
    for key in ("bossIds", "mimicEnemyIds"):
        for eid in gc.get(key) or []:
            if eid:
                enemy_ids.add(str(eid))

    level_ids = sorted(collect_theme_level_ids(detail))
    if not level_ids:
        return enemy_ids

    def _one(lid: str) -> set[str]:
        try:
            path = ensure_level_file(lid, download=download_missing)
            if not path:
                return set()
            data = json.loads(path.read_text(encoding="utf-8"))
            return enemies_from_level_json(data)
        except Exception as e:
            logger.warning(f"主题 {theme_id} 关卡 {lid} 解析失败: {e}")
            return set()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = [pool.submit(_one, lid) for lid in level_ids]
        for fut in as_completed(futs):
            enemy_ids |= fut.result()

    return enemy_ids


def sync_all_theme_levels(topic_table: dict[str, Any], *, max_workers: int = 4) -> dict[str, int]:
    """下载全部主题关卡 JSON（已存在则跳过）。"""
    details = topic_table.get("details") or {}
    all_ids: set[str] = set()
    for detail in details.values():
        if isinstance(detail, dict):
            all_ids |= collect_theme_level_ids(detail)

    ok = skip = fail = 0
    ordered = sorted(all_ids)
    total = len(ordered)
    print(f"  待检查关卡 {total} 个（并发 {max_workers}）", flush=True)

    def _dl(lid: str) -> str:
        rel = level_id_to_rel_path(lid)
        if not rel:
            return "fail"
        dest = local_level_path(rel)
        if dest.exists() and dest.stat().st_size > 50:
            return "skip"
        try:
            ensure_level_file(lid, download=True)
            return "ok"
        except Exception as e:
            logger.warning(f"关卡下载失败 {lid}: {e}")
            return "fail"

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_dl, lid): lid for lid in ordered}
        for fut in as_completed(futs):
            status = fut.result()
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                fail += 1
            done += 1
            if done % 25 == 0 or done == total:
                print(f"  进度 {done}/{total} ok={ok} skip={skip} fail={fail}", flush=True)

    logger.info(f"Roguelike levels sync: ok={ok} skip={skip} fail={fail} total={total}")
    return {"ok": ok, "skip": skip, "fail": fail, "total": total}


def iter_theme_details(topic_table: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    details = topic_table.get("details") or {}
    for tid, detail in details.items():
        if isinstance(detail, dict):
            yield tid, detail
