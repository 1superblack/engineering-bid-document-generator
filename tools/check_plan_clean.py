# -*- coding: utf-8 -*-
"""验证清洗后 planner 的章节规划。用法：python tools/check_plan_clean.py <tender_file>"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import _package_shim  # noqa: E402,F401

from bid_core.parser import parse_tender  # noqa: E402
from planner import plan_chapters  # noqa: E402
from scripts.bid_clean import clean_parse_result  # noqa: E402


def main() -> int:
    pr = clean_parse_result(parse_tender(sys.argv[1]))
    print("清洗后 technical_chapters:", len(pr.get("technical_chapters") or []))
    print("清洗后 score_items:", len(pr.get("score_items") or []))
    plan = plan_chapters(parse_result=pr, target_pages=200)
    chs = plan.get("chapters") or []
    print(f"规划章节数: {len(chs)}（来源={plan.get('source')}，detail_level={plan.get('detail_level')}）")
    for c in chs:
        print(f"  {c['title'][:52]} | target={c.get('target_pages')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
