"""
评审检查模块 v2.0
对标书进行专业评分和评审分析

模块结构:
- scoring: 评分标准定义（ScoringCriteria/ScoreItem）
- analyzer: 分析引擎（EvaluatorEngine/ComparativeEvaluator）
"""

from .analyzer import EvaluatorEngine, ComparativeEvaluator
from .scoring import (
    ScoringCriteria,
    ScoreItem,
    TECHNICAL_BID_CRITERIA,
    COMMERCIAL_BID_CRITERIA,
    get_criteria_for_bid_type,
    calculate_total_weight,
    validate_criteria,
)

__all__ = [
    # 核心类
    'EvaluatorEngine',
    'ComparativeEvaluator',
    # 数据模型
    'ScoringCriteria',
    'ScoreItem',
    # 预定义标准
    'TECHNICAL_BID_CRITERIA',
    'COMMERCIAL_BID_CRITERIA',
    # 辅助函数
    'get_criteria_for_bid_type',
    'calculate_total_weight',
    'validate_criteria',
]

__version__ = '2.0.0'
