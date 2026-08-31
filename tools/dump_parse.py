# -*- coding: utf-8 -*-
"""转储招标文件解析出的评分项明细。用法：python tools/dump_parse.py <tender_file>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import _package_shim  # noqa: E402,F401

from bid_core.parser import parse_tender  # noqa: E402


def main() -> int:
    pr = parse_tender(sys.argv[1])
    si = pr.get("score_items") or []
    print("评分项总数:", len(si))
    if si:
        print("字段示例:", json.dumps(si[0], ensure_ascii=False)[:400])
    print("\n--- 全部 (score | name) ---")
    for it in si:
        name = (it.get("name") or it.get("title") or "")[:50]
        print(f"{str(it.get('score', it.get('weight', ''))):>8} | {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
