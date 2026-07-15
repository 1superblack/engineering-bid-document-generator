"""
富内容引擎模块 v2.0
用于根据评分项配置动态生成章节内容

模块结构:
- utils: 基础工具函数（模板轮转、文本处理等）
- sentence_generators: 句子生成器（各专业领域）
- renderer: 核心渲染引擎（RichChapter类）
"""

from .renderer import RichChapter, resolve_chapter_class
from .utils import (
    _rotate,
    reset_rotation,
    get_current_rotation,
    format_number,
    safe_truncate,
)
from .sentence_generators import (
    SentenceGenerator,
    DomainSentenceGenerator,
    TechnicalSentenceGenerator,
    MeasureSentenceGenerator,
)
from .flavor_pools import (
    _POOL_ROTATION,
    _TECH10_POOL, _SEASON_POOL, _RISK_POOL, _AWARD_POOL,
    _BIM_POOL, _GREEN_POOL, _DEFECT_POOL, _SMART_POOL,
    _PROTECT_POOL, _MEASURE_POOL, _EMERGENCY_POOL,
    _CIVIL_POOL, _LABOR_POOL, _COORD_POOL,
)

__all__ = [
    # 核心类
    'RichChapter',
    'resolve_chapter_class',
    # 工具函数
    '_rotate',
    'reset_rotation',
    'get_current_rotation',
    'format_number',
    'safe_truncate',
    # 生成器
    'SentenceGenerator',
    'DomainSentenceGenerator',
    'TechnicalSentenceGenerator',
    'MeasureSentenceGenerator',
    # v8.1 flavor 句池
    '_POOL_ROTATION',
    '_TECH10_POOL', '_SEASON_POOL', '_RISK_POOL', '_AWARD_POOL',
    '_BIM_POOL', '_GREEN_POOL', '_DEFECT_POOL', '_SMART_POOL',
    '_PROTECT_POOL', '_MEASURE_POOL', '_EMERGENCY_POOL',
    '_CIVIL_POOL', '_LABOR_POOL', '_COORD_POOL',
]

__version__ = '2.0.0'
