"""pytest conftest — 配置 Python 路径和公共 fixtures

v8.0 修复: 原配置指向不存在的 scripts/ 目录且 PROJECT_ROOT 指向上一级。
现在 conftest.py 所在目录即为项目根目录（扁平化结构），直接将其加入 sys.path。
若存在 scripts/ 子目录（正式部署环境），也一并加入。
"""
import sys
from pathlib import Path

import pytest

# 项目根目录 = conftest.py 所在目录
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 兼容正式部署环境：若 scripts/ 存在则加入
SCRIPTS_DIR = PROJECT_ROOT / 'scripts'
if SCRIPTS_DIR.is_dir() and str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# v8.1: 包结构垫片 — 将扁平化模块映射为 bid_core/bid_technical 包路径
import _package_shim  # noqa: E402,F401

# v8.2: 预加载关键模块（按需 shim 已保证可解析，此处仅做热启动以摊薄 import 成本）。
# 单个模块加载失败不影响整体（非致命）。
_PRELOAD_MODULES = [
    'bid_core.logger',
    'bid_core.user_context',
    'bid_core.formatter',
    'bid_core.models',
    'bid_core.data_loader',
    'bid_core.parser',
    'bid_core.score_response',
    'bid_core.llm_client',
    'bid_core.deviation_checker',
    'bid_core.reference_loader',
    'bid_core.chapter_generator',
    'bid_technical.chapters.base',
    'bid_technical.generator',
    'bid_technical.evaluator_check',
    'bid_technical.tables.gantt',
    'bid_technical.tables.deviation_table',
    'evaluator',
    'checker',
    'scoring_strategy',
]
for _mod in _PRELOAD_MODULES:
    try:
        __import__(_mod)
    except Exception:  # noqa: BLE001 — 非致命，单个模块失败不影响整体
        pass


@pytest.fixture(scope='session')
def project_root():
    """返回项目根目录路径"""
    return PROJECT_ROOT
