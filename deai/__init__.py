"""
去AI化模块 v6.0
检测并替换标书中的AI写作特征，使标书更自然

模块结构:
- replacements: AI高频用词替换表（350条）
- detectors: AI特征检测器
- fixers: AI特征修复器
- domain_adjusters: 领域特定调整
- pipeline: 主处理管道和便捷接口
"""

from .pipeline import DeAIProcessor, deai_text, deai_docx
from .detectors import DeAIDetector
from .fixers import DeAIFixer
from .domain_adjusters import DomainAdjuster
from .replacements import (
    AI_PHRASE_REPLACEMENTS,
    ENGINEERING_PHRASES,
    DOMAIN_TERMS,
    OVERUSED_TRANSITION_WORDS,
)

__all__ = [
    # 主接口
    'DeAIProcessor',
    'deai_text',
    'deai_docx',
    # 子模块（高级用法）
    'DeAIDetector',
    'DeAIFixer',
    'DomainAdjuster',
    # 常量（可自定义）
    'AI_PHRASE_REPLACEMENTS',
    'ENGINEERING_PHRASES',
    'DOMAIN_TERMS',
    'OVERUSED_TRANSITION_WORDS',
]

__version__ = '6.0.0'
