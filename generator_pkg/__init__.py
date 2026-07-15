"""
Generator 包 - 技术标生成器模块 v7.0
从 generator.py (1585行) 拆分为4个模块

结构:
- tables.py: 附表数据模板
- core.py: 核心生成器类
- renderers.py: 渲染辅助方法
- __init__.py: 接口兼容层
"""

from .core import TechnicalBidGenerator
from .tables import TABLES, SERVICE_TABLES

__all__ = [
    'TechnicalBidGenerator',
    'TABLES',
    'SERVICE_TABLES',
]
