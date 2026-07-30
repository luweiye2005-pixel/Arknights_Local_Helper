"""通过 PRTS MediaWiki API 拉取词条为 Markdown，写入 data/wiki。

遵守限速，不爬 HTML。
用法:
  python scripts/sync_prts_wiki.py
  python scripts/sync_prts_wiki.py --titles 阿米娅 霜星
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "wiki"
API = "https://prts.wiki/api.php"

DEFAULT_TITLES = [
    "阿米娅",
    "能天使",
    "银灰",
    "推进之王",
    "集成战略",
    "集成战略/藏品",
    "敌人一览",
    "干员一览",
    "危机合约",
    "保全派驻",
]


def fetch_wikitext(client: httpx.Client, title: str) -> str | None:
    r = client.get(
        API,
        params={
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": title,
            "format": "json",
            "formatversion": 2,
        },
    )
    r.raise_for_status()
    data = r.json()
    pages = (data.get("query") or {}).get("pages") or []
    if not pages:
        return None
    page = pages[0]
    if page.get("missing"):
        return None
    revs = page.get("revisions") or []
    if not revs:
        return None
    slots = revs[0].get("slots") or {}
    main = slots.get("main") or {}
    return main.get("content") or revs[0].get("content")


def wikitext_to_markdown(title: str, wikitext: str) -> str:
    text = wikitext
    # 粗略清理模板与 wiki 语法，保留可读文本
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    # 多层模板简单剥离若干轮
    for _ in range(3):
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'{2,3}", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return f"# {title}\n\n来源: https://prts.wiki/w/{title}\n\n{text.strip()}\n"


def safe_filename(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", title)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--titles", nargs="*", default=None)
    parser.add_argument("--delay", type=float, default=0.8, help="请求间隔秒")
    args = parser.parse_args()
    titles = args.titles or DEFAULT_TITLES

    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    with httpx.Client(timeout=60.0, headers={"User-Agent": "ArknightsLocalAssistant/0.1 (local; educational)"}) as client:
        for title in titles:
            print(f"拉取: {title}")
            try:
                wt = fetch_wikitext(client, title)
                if not wt:
                    print("  missing")
                    continue
                md = wikitext_to_markdown(title, wt)
                path = OUT / f"{safe_filename(title)}.md"
                path.write_text(md, encoding="utf-8")
                print(f"  -> {path}")
                ok += 1
            except Exception as e:
                print(f"  ERROR: {e}")
            time.sleep(args.delay)
    print(f"完成 {ok}/{len(titles)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
