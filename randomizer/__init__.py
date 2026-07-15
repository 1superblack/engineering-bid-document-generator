"""
随机化引擎包 v6.0 (拆分版)

将原来的 randomizer.py（1240行）拆分为：
- core.py: 核心类 + 基础方法 (~250行)
- sentence_transforms.py: 句式变换策略 (~200行)
- table_randomizer.py: 表格数据随机化 (~350行)
- date_utils.py: 日期工具函数 (~80行)

对外接口保持完全不变：from bid_core.randomizer import Randomizer
"""

from .core import RandomizerCore
from .sentence_transforms import (
    SentenceTransforms,
    get_paragraph_start,
    get_transition_word,
    PARAGRAPH_STARTERS,
    TRANSITION_WORDS,
)
from .table_randomizer import TableRandomizer
from .date_utils import generate_date_range


class Randomizer(RandomizerCore, TableRandomizer):
    """
    随机化引擎 v6.0（组合版）

    继承核心功能 + 表格随机化能力，保持与原Randomizer类完全兼容的接口。
    """

    def __init__(self, synonyms_path=None, enabled=False):
        # 初始化核心功能
        RandomizerCore.__init__(self, synonyms_path=synonyms_path, enabled=enabled)

        # 初始化表格随机化
        TableRandomizer.__init__(self, enabled=enabled)

        # 引用句式变换工具类（用于实例方法调用）
        self._sentence_transforms = SentenceTransforms()

    def transform_sentence(self, text: str) -> str:
        """句式变换 v6.0增强版"""
        return SentenceTransforms.apply_random_transform(text, self.enabled)

    def _transform_active_passive(self, text: str) -> str:
        """主被动变换"""
        return SentenceTransforms.transform_active_passive(text)

    def _transform_long_short(self, text: str) -> str:
        """长短句变换"""
        return SentenceTransforms.transform_long_short(text)

    def _transform_affirm_negate(self, text: str) -> str:
        """肯定否定互换"""
        return SentenceTransforms.transform_affirm_negate(text)

    def _transform_legacy(self, text: str) -> str:
        """原有句式变换规则"""
        return SentenceTransforms.transform_legacy(text)

    def paragraph_start(self, default=''):
        """随机选择段落开头词"""
        return get_paragraph_start(self.enabled, default)

    def transition_word(self):
        """随机选择过渡词"""
        return get_transition_word(self.enabled)

    # 保留常量引用（向后兼容）
    SENTENCE_TRANSFORMS = SentenceTransforms.SENTENCE_TRANSFORMS
    ACTIVE_PASSIVE_RULES = SentenceTransforms.ACTIVE_PASSIVE_RULES
    AFFIRM_NEGATE_PAIRS = SentenceTransforms.AFFIRM_NEGATE_PAIRS
    LONG_SENTENCE_THRESHOLD = SentenceTransforms.LONG_SENTENCE_THRESHOLD
    PARAGRAPH_STARTERS = PARAGRAPH_STARTERS
    TRANSITION_WORDS = TRANSITION_WORDS

    # 表格方法映射
    randomize_table_data = TableRandomizer.randomize_table
    vary_table_data = TableRandomizer.vary_table_data

    # 日期方法
    generate_date_range = staticmethod(generate_date_range)


# ════════════════════════════════════════════════════════
# 向后兼容：保留顶层函数接口（如果有代码直接调用）
# ════════════════════════════════════════════════════════

# 导出常用工具函数（方便单独使用）
__all__ = [
    'Randomizer',
    'RandomizerCore',
    'SentenceTransforms',
    'TableRandomizer',
    'generate_date_range',
    'get_paragraph_start',
    'get_transition_word',
]
