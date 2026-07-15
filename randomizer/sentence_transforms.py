"""
句式变换策略 v6.0

提供文本的句式多样性变换能力：主被动转换、长短句、肯定否定等。
"""

import re
import random
from typing import Dict, Callable, Pattern

from log_helper import get_logger
log = get_logger(__name__)


class SentenceTransforms:
    """句式变换策略集合"""

    # 主被动语态变换规则
    ACTIVE_PASSIVE_RULES = [
        {
            'pattern': r'(.*?)(负责|承担|完成|实施|执行|组织|编制|落实|开展)(.*?)([。；])',
        },
    ]

    # 长句判定阈值（字数）
    LONG_SENTENCE_THRESHOLD: int = 40

    # 肯定否定互换对
    AFFIRM_NEGATE_PAIRS: list = [
        ('确保', '力争'),
        ('保证', '努力'),
        ('必须', '应当'),
        ('严格', '认真'),
    ]

    # 旧版句式变换模板（向后兼容）
    SENTENCE_TRANSFORMS: Dict[str, Callable] = {
        '为了(.+?)，(.+)': lambda m: f'{m.group(2)}，以实现{m.group(1)}',
        '通过(.+?)，可以(.+)': lambda m: f'{m.group(1)}的应用使{m.group(2)}成为可能',
        '需要(.+?)。': lambda m: f'{m.group(1)}是必要的。',
    }

    @staticmethod
    def transform_active_passive(text: str) -> str:
        """主被动变换"""
        result = text
        for rule in SentenceTransforms.ACTIVE_PASSIVE_RULES:
            pattern = rule['pattern']
            matches = list(re.finditer(pattern, result))
            if matches and random.random() < 0.5:
                m = random.choice(matches)
                subject = m.group(1)
                verb = m.group(2)
                obj = m.group(3).strip()
                punc = m.group(4)

                # 构建被动句
                passive_verbs = {
                    '负责': '负责',
                    '承担': '承担',
                    '完成': '完成',
                    '实施': '实施',
                    '执行': '执行',
                    '组织': '组织',
                    '编制': '编制',
                    '落实': '落实',
                    '开展': '开展',
                }
                pv = passive_verbs.get(verb, verb)
                passive_sent = f'{obj}由{subject}{pv}{punc}'
                result = result[:m.start()] + passive_sent + result[m.end():]
                break  # 每次只变换一句
        return result

    @staticmethod
    def transform_long_short(text: str) -> str:
        """长短句变换"""
        result = text

        # 查找长句（超过阈值字数且含逗号）
        sentences = re.split(r'([。；])', result)
        for i in range(0, len(sentences) - 1, 2):
            sent = sentences[i]
            punc = sentences[i + 1] if i + 1 < len(sentences) else '。'

            if len(sent) > SentenceTransforms.LONG_SENTENCE_THRESHOLD and '，' in sent:
                # 在适当逗号处拆分为两句
                commas = [m.start() for m in re.finditer(r'，', sent)]
                if commas:
                    # 选择中间偏后的逗号位置拆分
                    mid = commas[len(commas) // 2]
                    first_part = sent[:mid]
                    second_part = sent[mid + 1:]

                    # 50%概率拆分
                    if random.random() < 0.5:
                        sentences[i] = first_part + '。'
                        sentences[i + 1] = punc + second_part + punc
                        break

        result = ''.join(sentences)
        return result

    @staticmethod
    def transform_affirm_negate(text: str) -> str:
        """肯定否定互换"""
        result = text
        for affirm, negate in SentenceTransforms.AFFIRM_NEGATE_PAIRS:
            if affirm in result and random.random() < 0.3:
                # 只替换第一个匹配，且30%概率
                result = result.replace(affirm, negate, 1)
                break
        return result

    @staticmethod
    def transform_legacy(text: str) -> str:
        """原有句式变换规则（向后兼容）"""
        rules = list(SentenceTransforms.SENTENCE_TRANSFORMS.items())
        random.shuffle(rules)

        for pattern, transform in rules:
            match = re.search(pattern, text)
            if match:
                try:
                    return transform(match)
                except Exception:
                    return text

        return text

    @classmethod
    def apply_random_transform(cls, text: str, enabled: bool = True) -> str:
        """
        应用随机句式变换

        Args:
            text: 原始文本
            enabled: 是否启用随机化

        Returns:
            变换后的文本
        """
        if not enabled:
            return text

        # 30%概率不做变换
        if random.random() < 0.3:
            return text

        # 随机选择变换类型
        transform_type = random.choice(['active_passive', 'long_short', 'affirm_negate', 'legacy'])

        transforms = {
            'active_passive': cls.transform_active_passive,
            'long_short': cls.transform_long_short,
            'affirm_negate': cls.transform_affirm_negate,
            'legacy': cls.transform_legacy,
        }

        return transforms[transform_type](text)


# 段落开头词库 (v6.0: 80种)
PARAGRAPH_STARTERS: list = [
    '首先，', '其次，', '此外，', '同时，', '另外，',
    '在施工过程中，', '针对本项目，', '结合工程实际，',
    '具体而言，', '在此基础上，', '值得注意的是，',
    '从质量角度，', '从安全角度，', '从进度角度，',
    '一方面，', '另一方面，', '综上所述，',
    # ... 更多开头词
]

# 过渡词库 (v6.0: 60种)
TRANSITION_WORDS: list = [
    '因此，', '进而，', '从而，', '此外，', '同时，',
    '在此基础上，', '不仅如此，', '更重要的是，',
    '与此同时，', '除此之外，', '进一步而言，',
    # ... 更多过渡词
]


def get_paragraph_start(enabled: bool = True, default: str = '') -> str:
    """随机选择段落开头词"""
    if not enabled:
        return default
    return random.choice(PARAGRAPH_STARTERS)


def get_transition_word(enabled: bool = True) -> str:
    """随机选择过渡词"""
    if not enabled:
        return ''
    return random.choice(TRANSITION_WORDS)
