"""
文档查重模块 v2.0
支持多文件两两比对、文本语义查重、表格查重、通用条款过滤、元数据查重

模块结构:
- models: 数据模型（段落、表格、匹配结果等）
- extractors: 文档提取（Word/PDF）
- comparators: 比较算法（语义/Jaccard/表格）
- checker: 主查重引擎（DuplicateChecker类）
- report: 报告生成和输出
"""

from .checker import DuplicateChecker, check_duplicates
from .models import Paragraph, TableData, DuplicateMatch, MetadataInfo
from .extractors import (
    extract_document,
    get_whitelist,
    filter_common_clauses,
)
from .comparators import (
    SemanticChecker,
    JaccardChecker,
    calculate_risk_level,
)
from .report import print_report, generate_json_report, save_report

__all__ = [
    # 主接口
    'DuplicateChecker',
    'check_duplicates',
    # 数据模型
    'Paragraph',
    'TableData',
    'DuplicateMatch',
    'MetadataInfo',
    # 子模块
    'SemanticChecker',
    'JaccardChecker',
    # 工具函数
    'extract_document',
    'get_whitelist',
    'filter_common_clauses',
    'calculate_risk_level',
    # 报告
    'print_report',
    'generate_json_report',
    'save_report',
]

__version__ = '2.0.0'
