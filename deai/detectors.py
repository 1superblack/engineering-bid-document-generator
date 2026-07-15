"""
去AI化检测模块
包含所有AI特征检测方法
"""
import re
from typing import List, Dict
from collections import Counter

from log_helper import get_logger

log = get_logger(__name__)

from .replacements import (
    OVERUSED_TRANSITION_WORDS,
    TRANSITION_OVERUSE_THRESHOLD,
    CONSECUTIVE_PATTERN_THRESHOLD,
    AI_CLICHE_PATTERNS,
)


class DeAIDetector:
    """AI特征检测器"""

    def __init__(self):
        self.stats = {
            'parallel_structures_detected': 0,
            'repetitive_sentences_detected': 0,
            'transition_overuse_detected': 0,
            'consecutive_pattern_detected': 0,
            'cliche_patterns_detected': 0,
        }

    def detect_parallel_structure(self, text: str) -> List[Dict]:
        """检测首先/其次/最后等排列式排比结构"""
        issues = []
        parallel_patterns = [
            r'(首先|第一|其一|一是)[，,]([^。]+?)(其次|第二|其二|二是)[，,]([^。]+?)(最后|第三|其三|三是)[，,]',
            r'(一方面)[，,]([^。]+?)(另一方面)[，,]',
        ]
        for pat in parallel_patterns:
            for m in re.finditer(pat, text):
                issues.append({
                    'type': 'parallel_structure',
                    'match': m.group()[:100],
                    'position': m.start(),
                    'suggestion': '拆分排比句为独立短句，或用项目符号替代',
                })
        return issues

    def detect_repetitive_sentence_structure(self, text: str) -> List[Dict]:
        """检测连续相同句式（如连续多个"通过X，实现Y"）"""
        issues = []
        sentences = re.split(r'[。；！？]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 6]

        if len(sentences) < 3:
            return issues

        # 提取每句的前4字作为句式指纹
        fingerprint = []
        for s in sentences:
            m = re.match(r'^([\u4e00-\u9fff]{1,4})[，,]', s)
            if m:
                fingerprint.append(m.group(1))
            else:
                fingerprint.append(s[:4])

        # 检测连续3句以上句式相同
        for i in range(len(fingerprint) - 2):
            if fingerprint[i] == fingerprint[i+1] == fingerprint[i+2]:
                issues.append({
                    'type': 'repetitive_sentence',
                    'pattern': fingerprint[i],
                    'position': i,
                    'count': 3,
                    'suggestion': f'连续3句以「{fingerprint[i]}」开头，句式过于重复，建议变换表达',
                })
                break

        # 检测段落内重复句式比例
        counter = Counter(fingerprint)
        for pattern, count in counter.most_common(3):
            if count >= 4 and count / len(fingerprint) > 0.25:
                issues.append({
                    'type': 'repetitive_sentence_ratio',
                    'pattern': pattern,
                    'count': count,
                    'ratio': round(count / len(fingerprint), 2),
                    'suggestion': f'「{pattern}」句式占比{round(count/len(fingerprint)*100)}%，过高，建议分散变换',
                })

        return issues

    def detect_transition_overuse(self, text: str) -> List[Dict]:
        """检测过度使用过渡词"""
        issues = []
        for word in OVERUSED_TRANSITION_WORDS:
            count = text.count(word)
            if count > TRANSITION_OVERUSE_THRESHOLD:
                issues.append({
                    'type': 'transition_overuse',
                    'pattern': word,
                    'count': count,
                    'threshold': TRANSITION_OVERUSE_THRESHOLD,
                    'suggestion': f'「{word}」出现{count}次，超过阈值{TRANSITION_OVERUSE_THRESHOLD}次，建议替换部分为其他表述',
                })
        return issues

    def detect_consecutive_pattern(self, text: str) -> List[Dict]:
        """v6.0: 连续句式检测 — 超过阈值句相同句式标记为AI嫌疑"""
        issues = []
        sentences = re.split(r'[。；！？]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 6]

        if len(sentences) < CONSECUTIVE_PATTERN_THRESHOLD:
            return issues

        # 构建句式指纹：提取句首关键词模式
        VERB_PREFIXES = ['通过', '采用', '运用', '实施', '落实', '推进', '开展',
                         '建立', '完善', '强化', '加强', '优化', '确保', '实现',
                         '坚持', '执行', '按照', '依据', '根据', '围绕', '结合']
        PREP_PREFIXES = ['在', '对', '为', '以', '从', '将', '把', '与', '同']

        fingerprints = []
        for s in sentences:
            fp = None
            for vp in VERB_PREFIXES:
                if s.startswith(vp):
                    fp = f'V:{vp}'
                    break
            if fp is None:
                for pp in PREP_PREFIXES:
                    if s.startswith(pp):
                        fp = f'P:{pp}'
                        break
            if fp is None:
                m = re.match(r'^([\u4e00-\u9fff]{2})[，,]([\u4e00-\u9fff]{0,2})', s)
                if m:
                    fp = f'S:{m.group(1)}+{m.group(2)}'
                else:
                    fp = f'O:{s[:2]}'
            fingerprints.append(fp)

        # 滑动窗口检测连续相同指纹
        i = 0
        while i < len(fingerprints):
            j = i + 1
            while j < len(fingerprints) and fingerprints[j] == fingerprints[i]:
                j += 1
            consecutive_count = j - i
            if consecutive_count >= CONSECUTIVE_PATTERN_THRESHOLD:
                fp = fingerprints[i]
                fp_type = fp.split(':')[0]
                fp_key = fp.split(':')[1] if ':' in fp else fp

                type_labels = {'V': '动词', 'P': '介词', 'S': '句式', 'O': '其他'}
                type_label = type_labels.get(fp_type, '')

                issues.append({
                    'type': 'consecutive_pattern',
                    'pattern': fp_key,
                    'pattern_type': type_label,
                    'count': consecutive_count,
                    'start_sentence': i,
                    'threshold': CONSECUTIVE_PATTERN_THRESHOLD,
                    'suggestion': f'连续{consecutive_count}句使用相同{type_label}「{fp_key}」开头，超过阈值{CONSECUTIVE_PATTERN_THRESHOLD}，存在AI嫌疑，建议变换表达方式',
                })
                self.stats['consecutive_pattern_detected'] += 1
            i = j

        return issues

    def detect_cliche_patterns(self, text: str) -> List[Dict]:
        """v6.0: 检测AI套话模式（首先...其次...最后...等）"""
        issues = []

        for cliche in AI_CLICHE_PATTERNS:
            pattern, label = cliche if isinstance(cliche, tuple) else (cliche, 'AI套话')
            for m in re.finditer(pattern, text):
                issues.append({
                    'type': 'cliche_pattern',
                    'label': label,
                    'match': m.group()[:80],
                    'position': m.start(),
                    'suggestion': f'检测到「{label}」模式，建议打散或重写',
                })

        self.stats['cliche_patterns_detected'] += len(issues)
        return issues

    def check_term_density(self, text: str) -> Dict:
        """检查专业术语密度"""
        # 简化实现，实际逻辑见原文件
        from .replacements import DOMAIN_TERMS

        total_terms = sum(len(terms) for terms in DOMAIN_TERMS.values())
        found_terms = 0

        for domain, terms in DOMAIN_TERMS.items():
            for term in terms:
                if term in text:
                    found_terms += 1

        text_len = len(text)
        density = (found_terms / max(text_len, 1)) * 100

        return {
            'found_terms': found_terms,
            'total_available': total_terms,
            'density_pct': round(density, 2),
            'is_low': density < 3.0,
        }

    def detect_all(self, text: str) -> List[Dict]:
        """执行所有AI特征检测"""
        all_issues = []

        # 运行所有检测器
        detectors = [
            self.detect_parallel_structure(text),
            self.detect_repetitive_sentence_structure(text),
            self.detect_transition_overuse(text),
            self.detect_consecutive_pattern(text),
            self.detect_cliche_patterns(text),
        ]

        for detector_issues in detectors:
            all_issues.extend(detector_issues)

        self.stats['patterns_detected'] = len(all_issues)
        return all_issues
