# -*- coding: utf-8 -*-
"""转储规划器实际使用的章节列表与过滤逻辑。用法：python tools/dump_planner.py <tender_file>"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import _package_shim  # noqa: E402,F401

from bid_core.parser import parse_tender  # noqa: E402
from planner import _filter_valid_score_items, plan_chapters  # noqa: E402


def main() -> int:
    pr = parse_tender(sys.argv[1])
    print("technical_chapters 数量:", len(pr.get("technical_chapters") or []))
    for it in (pr.get("technical_chapters") or []):
        print("  TC:", (it.get("name") or "")[:60], "|", it.get("score"))
    print("\n评分项过滤前:", len(pr.get("score_items") or []),
          "过滤后:", len(_filter_valid_score_items(pr.get("score_items") or [])))
    for it in _filter_valid_score_items(pr.get("score_items") or []):
        print("  SI:", (it.get("name") or "")[:60], "|", it.get("score"))
    print("\n规划章节:")
    chs = plan_chapters(parse_result=pr, target_pages=100)
    for c in chs:
        print(f"  {c.get('source')} | {c['title'][:55]} | target={c.get('target_pages')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
