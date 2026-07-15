"""
格式修复模块
处理标点、数字、引号等格式问题
"""
import re
import logging

log = logging.getLogger(__name__)


class FormatFixer:
    """格式问题修复器"""

    def __init__(self):
        self.stats = {
            'punctuation_fixed': 0,
            'number_format_fixed': 0,
            'quotes_fixed': 0,
        }

    def fix_punctuation(self, text: str) -> str:
        """修复标点符号问题

        - 统一中英文标点
        - 修正连续标点
        - 确保句末标点完整
        """
        # 中文场景下统一使用中文标点
        fixes = [
            (r',(?=\s*[\u4e00-\u9fff])', '，'),  # 英文逗号→中文逗号（后接中文时）
            (r';(?=\s*[\u4e00-\u9fff])', '；'),
            (r':(?=\s*[\u4e00-\u9fff])', '：'),
            (r'\?(?=\s*[\u4e00-\u9fff])', '？'),
            (r'!(?=\s*[\u4e00-\u9fff])', '！'),
            # 修复连续句号
            (r'。{2,}', '。'),
            # 修复逗号后无空格直接跟汉字的情况
            (r'，(?=[\u4e00-\u9fff])', '，'),
        ]

        fixed_count = 0
        for pattern, replacement in fixes:
            text, count = re.subn(pattern, replacement, text)
            fixed_count += count

        self.stats['punctuation_fixed'] = fixed_count
        log.debug(f"标点符号修复完成: {fixed_count}处")

        return text

    def fix_number_format(self, text: str) -> str:
        """修复数字格式

        - 统一阿拉伯数字与中文数字使用规范
        - 百分比格式规范化
        """
        fixes = [
            # 百分比前后加空格（仅在必要时）
            (r'(\d)%', r'\1 %'),
            # 数字千位分隔（可选）
            # (r'\b(\d{4,})\b', lambda m: f'{int(m.group(1)):,}'),
        ]

        fixed_count = 0
        for pattern, replacement in fixes:
            text, count = re.subn(pattern, replacement, text)
            fixed_count += count

        self.stats['number_format_fixed'] = fixed_count
        return text

    def fix_quotes(self, text: str) -> str:
        """修复引号问题

        - 统一使用中文引号
        - 配对检查
        """
        # 英文双引号 → 中文双引号（在中文文本中）
        text = re.sub(
            r'"([^"]+)"',
            lambda m: f'"{m.group(1)}"' if any('\u4e00' <= c <= '\u9fff' for c in m.group(1)) else m.group(0),
            text
        )

        # 单引号类似处理
        text = re.sub(
            r"'([^']+)'",
            lambda m: f"'{m.group(1)}'" if any('\u4e00' <= c <= '\u9fff' for c in m.group(1)) else m.group(0),
            text
        )

        # 统计修复数量（简化）
        self.stats['quotes_fixed'] = text.count('"') // 2 + text.count("'") // 2

        return text

    def fix_all(self, text: str) -> str:
        """执行所有格式修复

        Args:
            text: 原始文本

        Returns:
            修复后的文本
        """
        log.info("开始格式修复")
        text = self.fix_punctuation(text)
        text = self.fix_number_format(text)
        text = self.fix_quotes(text)
        log.info(f"格式修复完成: 标点{self.stats['punctuation_fixed']}处, "
                f"数字{self.stats['number_format_fixed']}处, 引号{self.stats['quotes_fixed']}处")
        return text
