"""
随机化引擎核心 v6.0

提供基础的随机化能力：同义词替换、列表打乱、随机数生成等。
"""
import random
import json
import os
from typing import List, Dict, Optional

from log_helper import get_logger
log = get_logger(__name__)


class RandomizerCore:
    """随机化引擎核心功能"""

    def __init__(self, synonyms_path: Optional[str] = None, enabled: bool = False):
        """
        初始化随机化引擎

        Args:
            synonyms_path: 同义词表JSON文件路径
            enabled: 是否启用随机化，默认False（向后兼容）
        """
        self.enabled = enabled
        self.synonyms: Dict[str, List[str]] = {}
        if synonyms_path and os.path.exists(synonyms_path):
            with open(synonyms_path, 'r', encoding='utf-8') as f:
                self.synonyms = json.load(f)

    def enable(self) -> None:
        """启用随机化"""
        self.enabled = True

    def disable(self) -> None:
        """禁用随机化"""
        self.enabled = False

    def toggle(self, enabled: bool) -> None:
        """切换随机化状态"""
        self.enabled = enabled

    def synonym_replace(self, text: str) -> str:
        """
        同义词替换（如果启用）
        如果随机化未启用，返回原文
        """
        if not self.enabled:
            return text

        result = text
        for key, synonyms in self.synonyms.items():
            if key in result and synonyms:
                replacement = random.choice(synonyms)
                result = result.replace(key, replacement)
        return result

    def shuffle(self, items: list, seed: Optional[int] = None) -> list:
        """
        打乱列表顺序（如果启用）
        如果随机化未启用，返回原列表
        """
        if not self.enabled:
            return items

        if seed is not None:
            random.seed(seed)

        shuffled = items.copy()
        random.shuffle(shuffled)
        return shuffled

    def random_paragraph_count(self, base_count: int, variance: int = 2) -> int:
        """
        随机化段落数量

        Args:
            base_count: 基础数量
            variance: 波动范围

        Returns:
            在 base_count ± variance 范围内的随机数
        """
        if not self.enabled:
            return base_count

        return max(0, base_count + random.randint(-variance, variance))

    def gantt_offset(self, base_day: int, offset_range: int = 2) -> int:
        """横道图日期偏移"""
        if not self.enabled:
            return base_day
        return base_day + random.randint(-offset_range, offset_range)

    def choice(self, items: list):
        """从列表中随机选择一个元素"""
        if not self.enabled or not items:
            return items[0] if items else None
        return random.choice(items)

    def select_random_items(
        self,
        items: list,
        min_count: Optional[int] = None,
        max_count: Optional[int] = None
    ) -> list:
        """
        从列表中随机选择若干项

        Args:
            items: 原始列表
            min_count: 最少选择数量（默认len的50%）
            max_count: 最多选择数量（默认len的80%）

        Returns:
            随机选择的子列表
        """
        if not self.enabled:
            return items

        n = len(items)
        min_c = min_count or max(1, int(n * 0.5))
        max_c = max_count or max(min_c, int(n * 0.8))
        count = random.randint(min_c, min(max_c, n))

        return random.sample(items, count)
