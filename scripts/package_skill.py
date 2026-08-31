# -*- coding: utf-8 -*-
"""打包 skill 为发布 zip（排除缓存/测试/临时文件）。

用法：python scripts/package_skill.py [--out 输出.zip]
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", "tests", ".git"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def main() -> int:
    ap = argparse.ArgumentParser(description="打包 skill 为发布 zip")
    ap.add_argument("--out", default=None, help="输出 zip 路径（默认在 skill 上级目录）")
    args = ap.parse_args()
    out = Path(args.out) if args.out else ROOT.parent / f"{ROOT.name}.zip"
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(ROOT.rglob("*")):
            if p.is_dir():
                continue
            if any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            if p.suffix.lower() in EXCLUDE_SUFFIXES:
                continue
            zf.write(p, p.relative_to(ROOT.parent))
            count += 1
    print(f"已打包: {out}（{out.stat().st_size} bytes，{count} 个文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
