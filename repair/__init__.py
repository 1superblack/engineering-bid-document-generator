"""
修复模块 v2.0
对标书检查结果进行分析和修复

模块结构:
- utils: 修复工具函数（表格构建、标题检测等）
- format_fixer: 格式修复器（标点、数字、引号）
- engine: 主修复引擎（BidRepairer类）
"""

from .engine import BidRepairer, repair_bid
from .format_fixer import FormatFixer
from .utils import (
    _build_concrete_table,
    _re_match_heading,
    _re_detect_heading_level,
    REPAIR_TEMPLATES,
)

__all__ = [
    # 主接口
    'BidRepairer',
    'repair_bid',
    # 子模块
    'FormatFixer',
    # 工具函数
    '_build_concrete_table',
    '_re_match_heading',
    '_re_detect_heading_level',
    'REPAIR_TEMPLATES',
]

__version__ = '2.0.0'
