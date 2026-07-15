# -*- coding: utf-8 -*-
"""Lite 版可运行演示：最小工程信息 → 生成技术标书 docx。

运行：在仓库根目录执行  python examples/demo.py
依赖：pip install -r requirements.txt
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _package_shim  # noqa: F401  加载扁平模块→包路径映射

from main import generate_bid_document


def main():
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)

    project = {
        "name": "示例市某办公楼装饰装修工程施工",
        "work_content": "室内装饰装修、给排水、电气安装及消防工程",
        "duration": 180,
        "area": 12000,
        "bid_type": "construction",
        "detail_level": 2,
        "target_pages": 80,
        "output_path": str(out_dir / "demo_bid.docx"),
    }

    print("开始生成示例标书 ...")
    result = generate_bid_document(project)
    if result.get("success"):
        print(f"✅ 生成成功：{result['output_file']}")
    else:
        print(f"❌ 生成失败：{result.get('message')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
