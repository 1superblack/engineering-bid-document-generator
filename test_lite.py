"""Lite 版冒烟测试 — 验证核心引擎可导入并端到端生成技术标书。

这是 GitHub 开源 lite 版的自我保护测试，不依赖完整 tests/ 套件。
运行：在仓库根目录执行 `pytest test_lite.py -q`（需先 `pip install -r requirements.txt`）。

设计原则（与「脱敏发布」一致）：
- 仅验证「引擎 + 通用语料」可跑通，不触碰任何专有内容；
- 生成用最小工程信息，避免依赖完整评分项解析。
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import _package_shim  # noqa: E402,F401  加载扁平模块→包路径映射


def _sample_project(tmp_path: Path) -> dict:
    """最小可用工程信息（示例数据，无任何真实主体信息）。"""
    return {
        "name": "示例市某办公楼装饰装修工程施工",
        "work_content": "室内装饰装修、给排水、电气安装及消防工程",
        "duration": 180,
        "area": 12000,
        "bid_type": "construction",
        "detail_level": 1,
        "target_pages": 30,
        "enable_hooks": False,
        "enable_deviation_table": False,
        "enable_risk_grading": False,
        "enable_mock_review": False,
        "output_path": str(tmp_path / "bid_sample.docx"),
    }


def test_flavor_pools_loaded():
    """差异化句池（核心引擎的"弹药库"）可正常导入且非空。"""
    from base.flavor_pools import (
        _TECH10_POOL,
        _GREEN_POOL,
        _DOMAIN_POOL,
        _COORD_POOL,
    )
    assert len(_TECH10_POOL) >= 5
    assert len(_GREEN_POOL) >= 5
    assert "质量" in _DOMAIN_POOL
    assert len(_COORD_POOL) >= 5


def test_scoring_strategy_loaded():
    """评分策略库可加载且包含施工/服务两类策略。"""
    path = ROOT / "data" / "scoring_strategy.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "construction_strategy_db" in data
    assert "service_strategy_db" in data


def test_knowledge_base_is_sample():
    """企业知识库必须是脱敏样例数据（不含真实主体信息）。"""
    path = ROOT / "data" / "user_knowledge_base.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    company = data["company"]["name"]
    assert "示例" in company, "知识库应仅含脱敏样例数据"


def test_generate_technical_bid(tmp_path: Path):
    """端到端：最小工程信息 → 生成可读 docx。"""
    import main

    proj = _sample_project(tmp_path)
    result = main.generate_bid_document(proj)
    assert result.get("success") is True, result
    out = Path(result["output_file"])
    assert out.exists(), f"未生成输出文件: {out}"
    assert out.stat().st_size > 20_000, f"生成内容过小: {out.stat().st_size} bytes"
