"""
去AI化修复模块
包含所有AI特征修复和转换方法
"""
import re
import random
from typing import Tuple, Dict, List

from log_helper import get_logger
log = get_logger(__name__)


class DeAIFixer:
    """AI特征修复器"""

    def __init__(self, replacements: dict):
        self.replacements = replacements
        self.stats = {
            'phrases_replaced': 0,
            'consecutive_patterns_fixed': 0,
            'cliche_patterns_fixed': 0,
            'paragraph_starts_diversified': 0,
        }

    def fix_consecutive_patterns(self, text: str) -> Tuple[str, int]:
        """修复连续句式模式"""
        fixed_count = 0

        # 检测连续相同动词开头的句子并打散
        verb_prefixes = ['通过', '采用', '运用', '实施', '落实', '推进',
                         '开展', '建立', '完善', '强化', '加强']

        sentences = re.split(r'([。；！？])', text)
        new_sentences = []
        prev_prefix = None
        consecutive_count = 0

        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i]
            punct = sentences[i + 1] if i + 1 < len(sentences) else ''

            current_prefix = None
            for vp in verb_prefixes:
                if sentence.strip().startswith(vp):
                    current_prefix = vp
                    break

            # 如果与前一句前缀相同且已连续3句以上，替换当前前缀
            if (current_prefix and current_prefix == prev_prefix
                    and consecutive_count >= 2):
                alternatives = [v for v in verb_prefixes if v != current_prefix]
                if alternatives:
                    new_prefix = random.choice(alternatives)
                    sentence = new_prefix + sentence[len(current_prefix):]
                    fixed_count += 1
                    consecutive_count = 0
                else:
                    consecutive_count += 1
            elif current_prefix == prev_prefix:
                consecutive_count += 1
            else:
                consecutive_count = 0

            prev_prefix = current_prefix
            new_sentences.append(sentence)
            if punct:
                new_sentences.append(punct)

        self.stats['consecutive_patterns_fixed'] = fixed_count
        return ''.join(new_sentences), fixed_count

    def fix_cliche_patterns(self, text: str) -> Tuple[str, int]:
        """修复AI套话模式"""
        fixed_count = 0

        # 替换"首先...其次...最后..."为更自然的方式
        cliche_fixes = [
            (r'首先([，,])', r'\n• '),
            (r'其次([，,])', r'\n• '),
            (r'最后([，,])', r'\n• '),
            (r'一方面([，,])([^。]+?)(另一方面)', r'1. \2\n2. '),
        ]

        for pattern, replacement in cliche_fixes:
            matches = re.findall(pattern, text)
            if matches:
                text = re.sub(pattern, replacement, text)
                fixed_count += len(matches)

        self.stats['cliche_patterns_fixed'] = fixed_count
        return text, fixed_count

    def transform_purpose_clause(self, text: str) -> Tuple[str, int]:
        """转换目的状语从句（旨在/为了/为使...）"""
        fixed_count = 0

        purpose_patterns = [
            (r'旨在([^，。]+?)([，。])', r'目的是\1\2', ),
            (r'为了([^，。]+?)([，。])', r'为\1\2', ),
            (r'为使([^，。]+?)([，。])', r'为实现\1\2', ),
        ]

        for pattern, replacement in purpose_patterns:
            new_text, count = re.subn(pattern, replacement, text)
            if count > 0:
                text = new_text
                fixed_count += count

        self.stats['purpose_clauses_transformed'] = fixed_count
        return text, fixed_count

    def insert_transitions(self, text: str) -> Tuple[str, int]:
        """插入过渡词（在段落间增加自然过渡）"""
        inserted_count = 0

        # 在长段落间插入简单过渡
        paragraphs = text.split('\n\n')
        new_paragraphs = []

        transition_pool = [
            '在此基础上，',
            '与此同时，',
            '此外，',
            '具体而言，',
        ]

        for i, para in enumerate(paragraphs):
            if i > 0 and len(para) > 50:
                # 随机决定是否插入过渡词
                if random.random() < 0.3:  # 30%概率插入
                    transition = random.choice(transition_pool)
                    para = transition + para
                    inserted_count += 1
            new_paragraphs.append(para)

        text = '\n\n'.join(new_paragraphs)
        self.stats['transitions_inserted'] = inserted_count
        return text, inserted_count

    def fix_parallel_structures(self, text: str) -> Tuple[str, int]:
        """修复排比结构"""
        fixed_count = 0

        # 将"首先...其次...最后..."转换为列表形式
        parallel_fixes = [
            (
                r'(首先|第一|其一|一是)[，,]([^。]+?)(其次|第二|其二|二是)[，,]([^。]+?)(最后|第三|其三|三是)[，,]([^。]+?)。',
                lambda m: f'\n1. {m.group(2)}；\n2. {m.group(4)}；\n3. {m.group(6)}。'
            ),
        ]

        for pattern, replacement in parallel_fixes:
            new_text, count = re.subn(pattern, replacement, text)
            if count > 0:
                text = new_text
                fixed_count += count

        self.stats['parallel_structures_fixed'] = fixed_count
        return text, fixed_count

    def apply_replacements(self, text: str) -> Tuple[str, int]:
        """应用所有短语替换"""
        replaced_count = 0

        for old, new in self.replacements.items():
            if not old or not new:
                continue
            try:
                count = text.count(old)
                if count > 0:
                    text = text.replace(old, new)
                    replaced_count += count
            except Exception:
                continue

        self.stats['phrases_replaced'] = replaced_count
        return text, replaced_count

    def adjust_term_density(self, text: str, domain: str = None) -> Tuple[str, int]:
        """调整术语密度"""
        from .replacements import DOMAIN_TERMS

        adjustments = 0

        if domain and domain in DOMAIN_TERMS:
            terms = DOMAIN_TERMS[domain]
            for term in terms:
                if term not in text and random.random() < 0.1:
                    # 在随机位置插入术语
                    sentences = text.split('。')
                    if len(sentences) > 1:
                        insert_pos = random.randint(1, len(sentences) - 1)
                        sentences[insert_pos] += f"，涉及{term}等"
                        text = '。'.join(sentences)
                        adjustments += 1

        self.stats['term_density_adjustments'] = adjustments
        return text, adjustments
