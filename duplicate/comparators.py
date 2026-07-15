"""
查重比较算法模块
包含语义相似度、Jaccard相似度、表格比较等
"""
import re
import logging
from typing import List, Tuple, Dict, Set, Optional

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import jieba
    jieba.setLogLevel(jieba.INFO)
    HAS_JIEBA = True
except Exception:
    HAS_JIEBA = False

from .models import Paragraph, TableData, DuplicateMatch, MetadataInfo

log = logging.getLogger(__name__)


class SemanticChecker:
    """基于TF-IDF的语义相似度检查器"""

    def __init__(self):
        self.vectorizer = TfidfVectorizer() if HAS_SKLEARN else None

    def check(self, paragraphs_a: List[Paragraph],
              paragraphs_b: List[Paragraph],
              threshold: float = 0.8) -> List[DuplicateMatch]:
        """执行语义查重

        Args:
            paragraphs_a: 文档A的段落列表
            paragraphs_b: 文档B的段落列表
            threshold: 相似度阈值（0-1）

        Returns:
            重复匹配结果列表
        """
        if not HAS_SKLEARN:
            log.warning("未安装sklearn，无法进行语义查重")
            return []

        if not paragraphs_a or not paragraphs_b:
            return []

        try:
            # 分词
            texts_a = [self._tokenize(p.text) for p in paragraphs_a]
            texts_b = [self._tokenize(p.text) for p in paragraphs_b]

            all_texts = texts_a + texts_b

            # 向量化
            tfidf_matrix = self.vectorizer.fit_transform(all_texts)

            # 计算余弦相似度
            sim_matrix = cosine_similarity(tfidf_matrix[:len(texts_a)],
                                           tfidf_matrix[len(texts_a):])

            # 提取超过阈值的匹配对
            matches = []
            for i in range(len(texts_a)):
                for j in range(len(texts_b)):
                    if sim_matrix[i][j] >= threshold:
                        matches.append(DuplicateMatch(
                            source=paragraphs_a[i],
                            target=paragraphs_b[j],
                            similarity=float(sim_matrix[i][j]),
                            match_type='semantic',
                        ))

            log.info(f"语义查重完成: {len(matches)}个匹配对 (阈值={threshold})")
            return matches

        except Exception as e:
            log.error(f"语义查重计算出错: {e}")
            return []

    def _tokenize(self, text: str) -> str:
        """中文分词"""
        if HAS_JIEBA:
            return ' '.join(jieba.cut(text))
        # 简单按字符切分
        return ' '.join(list(text))


class JaccardChecker:
    """基于Jaccard相似度的辅助查重"""

    def check(self, paragraphs_a: List[Paragraph],
              paragraphs_b: List[Paragraph],
              threshold: float = 0.7) -> List[DuplicateMatch]:
        """执行Jaccard相似度查重

        基于字符级别的Jaccard系数计算
        """
        matches = []

        for para_a in paragraphs_a:
            set_a = self._get_char_set(para_a.text)

            for para_b in paragraphs_b:
                set_b = self._get_char_set(para_b.text)

                if not set_a or not set_b:
                    continue

                intersection = len(set_a & set_b)
                union = len(set_a | set_b)

                jaccard_sim = intersection / union if union > 0 else 0

                if jaccard_sim >= threshold:
                    matches.append(DuplicateMatch(
                        source=para_a,
                        target=para_b,
                        similarity=jaccard_sim,
                        match_type='jaccard',
                    ))

        log.info(f"Jaccard查重完成: {len(matches)}个匹配对")
        return matches

    @staticmethod
    def _get_char_set(text: str) -> Set[str]:
        """提取字符集合（过滤空白和标点）"""
        return set(c for c in text if c.strip() and c not in '，。；：""''！？（）【】《》')


def normalize_table_row(row: List[str]) -> str:
    """标准化表格行（用于比较）"""
    normalized = []
    for cell in row:
        cell = re.sub(r'\s+', '', cell)  # 移除空格
        cell = cell.lower()
        normalized.append(cell)
    return '|'.join(normalized)


def find_duplicate_table_rows(tables_a: List[TableData],
                              tables_b: List[TableData],
                              threshold: float = 0.9) -> List[Dict]:
    """查找重复的表格行

    Returns:
        重复行信息列表
    """
    duplicates = []

    rows_a = []  # (table_index, row_index, normalized_text)
    for ti, table in enumerate(tables_a):
        for ri, row in enumerate(table.rows):
            rows_a.append((ti, ri, normalize_table_row(row)))

    rows_b = []
    for ti, table in enumerate(tables_b):
        for ri, row in enumerate(table.rows):
            rows_b.append((ti, ri, normalize_table_row(row)))

    # 简单比较
    for ta, ra, norm_a in rows_a:
        for tb, rb, norm_b in rows_b:
            if norm_a and norm_a == norm_b:
                duplicates.append({
                    'source': f'表格{ta+1}行{ra+1}',
                    'target': f'表格{tb+1}行{rb+1}',
                    'content': norm_a,
                })

    log.debug(f"表格行重复检测: {len(duplicates)}组重复")
    return duplicates


def find_identical_tables(table_a: TableData, table_b: TableData) -> float:
    """计算两个表格的相似度

    Returns:
        0-1之间的相似度分数
    """
    if not table_a.rows or not table_b.rows:
        return 0.0

    # 标准化后逐行比较
    rows_a = [normalize_table_row(row) for row in table_a.rows]
    rows_b = [normalize_table_row(row) for row in table_b.rows]

    if not rows_a or not rows_b:
        return 0.0

    matches = sum(1 for ra in rows_a if ra in rows_b)
    similarity = matches / max(len(rows_a), len(rows_b))

    return similarity


def compare_metadata(meta_a: MetadataInfo, meta_b: MetadataInfo) -> Dict:
    """比较文档元数据

    Returns:
        比较结果字典，包含各项相似度和警告
    """
    result = {
        'author_same': meta_a.author == meta_b.author,
        'company_same': meta_a.company == meta_b.company,
        'created_date_same': meta_a.created_date == meta_b.created_date,
        'warnings': [],
        'risk_score': 0,
    }

    # 生成警告
    if result['author_same'] and meta_a.author:
        result['warnings'].append(f'作者相同: {meta_a.author}')
        result['risk_score'] += 30

    if result['company_same'] and meta_a.company:
        result['warnings'].append(f'公司相同: {meta_a.company}')
        result['risk_score'] += 40

    # 日期相近检查
    if _date_similar(meta_a.created_date, meta_b.created_date):
        result['warnings'].append('创建日期接近')
        result['risk_score'] += 20

    return result


def _str_similar(str1: str, str2: str) -> bool:
    """判断两个字符串是否相似（简单实现）"""
    if not str1 or not str2:
        return False

    # 完全相同或包含关系
    if str1 == str2 or str1 in str2 or str2 in str1:
        return True

    # 长度差异过大则不相似
    if abs(len(str1) - len(str2)) / max(len(str1), len(str2)) > 0.3:
        return False

    # 字符重叠率
    set1, set2 = set(str1), set(str2)
    overlap = len(set1 & set2) / max(len(set1), len(set2))
    return overlap > 0.8


def _date_similar(date1: str, date2: str) -> bool:
    """判断两个日期是否接近（3天内）"""
    from datetime import datetime

    try:
        d1 = datetime.fromisoformat(date1.replace('Z', '+00:00'))
        d2 = datetime.fromisoformat(date2.replace('Z', '+00:00'))
        diff = abs((d1 - d2).days)
        return diff <= 3
    except (ValueError, TypeError):
        return False


def calculate_risk_level(similarity: float,
                        metadata_risk: int = 0,
                        mode: str = "通用") -> Dict:
    """计算综合风险等级

    Args:
        similarity: 文本相似度 (0-100)
        metadata_risk: 元数据风险分数 (0-100)
        mode: 查重模式

    Returns:
        风险评估字典
    """
    # 综合评分
    total_score = similarity * 0.7 + metadata_risk * 0.3

    # 阈值设定（不同模式有不同标准）
    thresholds = {
        '标书': {'low': 30, 'medium': 50, 'high': 70},
        '论文': {'low': 20, 'medium': 40, 'high': 60},
        '通用': {'low': 25, 'medium': 45, 'high': 65},
    }
    thresh = thresholds.get(mode, thresholds['通用'])

    if total_score >= thresh['high']:
        level = '高风险'
    elif total_score >= thresh['medium']:
        level = '中等风险'
    elif total_score >= thresh['low']:
        level = '低风险'
    else:
        level = '安全'

    return {
        'total_score': round(total_score, 1),
        'similarity_score': round(similarity, 1),
        'metadata_score': metadata_risk,
        'risk_level': level,
        'thresholds': thresh,
    }
