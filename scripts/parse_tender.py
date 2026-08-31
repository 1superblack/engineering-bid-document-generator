# -*- coding: utf-8 -*-
"""解析招标文件并输出评分项摘要（一键解析）。

用法：
    python scripts/parse_tender.py --tender-file 招标文件.docx [--bid-type construction]

成功退出码 0；解析失败返回 2。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import _package_shim  # noqa: E402,F401  包结构垫片，必须最先导入

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _summarize(pr: dict) -> dict:
    """把 parse_result 压缩成可读摘要。"""
    score_items = pr.get("score_items") or []
    star_clauses = pr.get("star_clauses") or []
    red_lines = pr.get("red_line_clauses") or []
    quals = pr.get("qualification_reqs") or []
    forms = pr.get("form_requirements") or []

    def _label(item) -> str:
        if isinstance(item, dict):
            name = item.get("name") or item.get("title") or ""
            score = item.get("score") or item.get("weight") or ""
            return f"{name}（{score}分）" if score else name
        return str(item)

    return {
        "score_items": len(score_items),
        "star_clauses": len(star_clauses),
        "red_line_clauses": len(red_lines),
        "qualification_reqs": len(quals),
        "form_requirements": len(forms),
        "score_items_preview": [_label(x) for x in score_items[:15]],
        "star_clauses_preview": [_label(x) for x in star_clauses[:10]],
        "qualification_preview": [_label(x) for x in quals[:10]],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="解析招标文件（Word/PDF），输出评分项摘要")
    ap.add_argument("--tender-file", required=True, help="招标文件路径（.docx/.pdf）")
    ap.add_argument("--bid-type", choices=("construction", "service"), default="construction")
    ap.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    args = ap.parse_args()

    from bid_core.parser import parse_tender
    from bid_clean import clean_parse_result

    pr = parse_tender(args.tender_file, bid_type=args.bid_type)
    if pr.get("_error"):
        print(f"[解析失败] {pr['_error']}", file=sys.stderr)
        return 2
    pr = clean_parse_result(pr)

    summary = _summarize(pr)
    total = (summary["score_items"] + summary["star_clauses"]
             + summary["red_line_clauses"] + summary["qualification_reqs"])
    if total == 0:
        print("[解析失败] 未提取到评分项/星号/红线/资格要求。"
              "若是扫描件 PDF，请先 OCR；若文件为加密/图片型 docx，请先转成可复制文本。", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"评分项 {summary['score_items']} | 星号条款 {summary['star_clauses']} | "
              f"废标红线 {summary['red_line_clauses']} | 资格要求 {summary['qualification_reqs']} | "
              f"形式要求 {summary['form_requirements']}")
        if summary["score_items_preview"]:
            print("\n主要评分项：")
            for idx, item in enumerate(summary["score_items_preview"], 1):
                print(f"  {idx}. {item}")
        if summary["qualification_preview"]:
            print("\n资格要求（前10条）：")
            for idx, item in enumerate(summary["qualification_preview"], 1):
                print(f"  {idx}. {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
