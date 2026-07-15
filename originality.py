"""文档原创度自检 v7.6。

扫描生成标书正文内的重复 / 高度相似段落，给出原创度评分与重复片段定位。
对标钛投标「标书查重 98-100%」能力——我们的定位是「自查不雷同」：
让文档内部的字面重复率可量化、可核查，便于用户针对性改写，降低查重合规风险。

纯标准库实现（difflib），零依赖、零回归。
"""
import re
from difflib import SequenceMatcher

# 短段落（标题/列表项/提示语）噪声大，不参与两两比较
_MIN_LEN = 20
# 相似度阈值（>= 判定为高度相似）
_DEFAULT_THRESHOLD = 0.82


def _norm(text: str) -> str:
    """去除空白，便于稳定比较。"""
    return re.sub(r'\s+', '', text or '')


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def scan_originality(paragraphs: list, threshold: float = _DEFAULT_THRESHOLD) -> dict:
    """扫描段落列表，返回原创度自检结果。

    Returns:
        {
          'score': float,            # 原创度分 0-100
          'grade': str,              # 评级描述
          'total_paragraphs': int,   # 参与比较的段落数
          'repeated_paragraphs': int,# 被标注重复的段落数
          'repeated_pairs': list,    # 重复段落对（最多 20）
          'threshold': float,
        }
    """
    cleaned = [_norm(p) for p in (paragraphs or []) if p and len(_norm(p)) >= _MIN_LEN]
    n = len(cleaned)
    flagged = set()
    repeated_pairs = []

    for i in range(n):
        for j in range(i + 1, n):
            sim = _similarity(cleaned[i], cleaned[j])
            if sim >= threshold:
                repeated_pairs.append({
                    'index_a': i,
                    'index_b': j,
                    'similarity': round(sim, 3),
                    'text_a': (paragraphs[i] or '')[:50],
                    'text_b': (paragraphs[j] or '')[:50],
                })
                flagged.add(i)
                flagged.add(j)

    repeated_count = len(flagged)
    if n > 0:
        score = round(100.0 * (1.0 - repeated_count / n), 1)
    else:
        score = 100.0

    if score >= 95:
        grade = '优秀（极低重复，查重合规风险低）'
    elif score >= 85:
        grade = '良好（少量重复，可接受）'
    elif score >= 70:
        grade = '一般（存在明显重复段落，建议改写）'
    else:
        grade = '偏高（重复段落较多，强烈建议改写降重）'

    return {
        'score': score,
        'grade': grade,
        'total_paragraphs': n,
        'repeated_paragraphs': repeated_count,
        'repeated_pairs': repeated_pairs[:20],
        'threshold': threshold,
    }
