"""
文档查重引擎
主查重器类，协调文本提取、比较和报告生成
"""
import os
import logging
from typing import List, Dict, Tuple, Optional

from .models import Paragraph, TableData, MetadataInfo, DuplicateMatch
from .extractors import (
    extract_document,
    get_whitelist,
    filter_common_clauses,
)
from .comparators import (
    SemanticChecker,
    JaccardChecker,
    find_duplicate_table_rows,
    find_identical_tables,
    compare_metadata,
    calculate_risk_level,
)

log = logging.getLogger(__name__)


class DuplicateChecker:
    """文档查重引擎 v2.0

    支持功能：
    - 多文件两两比对
    - 文本语义查重（基于TF-IDF）
    - 表格内容查重
    - 通用条款过滤
    - 元数据查重（作者、公司、创建日期等）
    """

    def __init__(self, mode: str = '通用', threshold: float = 0.8):
        """
        Args:
            mode: 查重模式（标书/论文/通用）
            threshold: 相似度阈值（0-1），超过此值视为重复
        """
        self.mode = mode
        self.threshold = threshold

        # 初始化子模块
        self.semantic_checker = SemanticChecker()
        self.jaccard_checker = JaccardChecker()

        # 加载白名单
        self.whitelist = get_whitelist(mode)

        # 缓存已提取的文档
        self._doc_cache: Dict[str, Tuple[List[Paragraph], List[TableData], MetadataInfo]] = {}

        log.info(f"DuplicateChecker初始化 | 模式={mode} | 阈值={threshold}")

    def _extract_or_cache(self, file_path: str) -> Tuple[List[Paragraph], List[TableData], MetadataInfo]:
        """提取文档（带缓存）"""
        if file_path in self._doc_cache:
            return self._doc_cache[file_path]

        paragraphs, tables, meta = extract_document(file_path)
        self._doc_cache[file_path] = (paragraphs, tables, meta)
        return paragraphs, tables, meta

    def check_pair(self, file_a: str, file_b: str) -> Dict:
        """对两个文件执行完整查重

        Args:
            file_a: 文件A路径
            file_b: 文件B路径

        Returns:
            查重结果字典
        """
        log.info(f"开始查重: {os.path.basename(file_a)} vs {os.path.basename(file_b)}")

        # 提取文档
        paras_a, tables_a, meta_a = self._extract_or_cache(file_a)
        paras_b, tables_b, meta_b = self._extract_or_cache(file_b)

        # 过滤通用条款
        paras_a_filtered, filtered_a_count = filter_common_clauses(paras_a, self.whitelist)
        paras_b_filtered, filtered_b_count = filter_common_clauses(paras_b, self.whitelist)

        log.debug(f"过滤通用条款: A过滤{filtered_a_count}条, B过滤{filtered_b_count}条")

        # 执行各类查重
        semantic_matches = self.semantic_checker.check(
            paras_a_filtered, paras_b_filtered, self.threshold
        )
        jaccard_matches = self.jaccard_checker.check(
            paras_a_filtered, paras_b_filtered, self.threshold * 0.9
        )
        table_duplicates = find_duplicate_table_rows(tables_a, tables_b)

        # 合并结果（去重）
        all_matches = self._merge_matches(semantic_matches + jaccard_matches)

        # 计算相似度统计
        if all_matches:
            max_similarity = max(m.similarity for m in all_matches)
            avg_similarity = sum(m.similarity for m in all_matches) / len(all_matches)
        else:
            max_similarity = 0.0
            avg_similarity = 0.0

        # 元数据比较
        meta_comparison = compare_metadata(meta_a, meta_b)

        # 综合风险评估
        risk_assessment = calculate_risk_level(
            similarity=max_similarity * 100,
            metadata_risk=meta_comparison.get('risk_score', 0),
            mode=self.mode,
        )

        result = {
            'mode': self.mode,
            'files': [file_a, file_b],
            'documents': {
                os.path.basename(file_a): {
                    'file': file_a,
                    'paragraph_count': len(paras_a),
                    'table_count': len(tables_a),
                    'meta': meta_a.to_dict(),
                },
                os.path.basename(file_b): {
                    'file': file_b,
                    'paragraph_count': len(paras_b),
                    'table_count': len(tables_b),
                    'meta': meta_b.to_dict(),
                },
            },
            'overall_similarity': round(max_similarity * 100, 1),
            'avg_similarity': round(avg_similarity * 100, 1),
            'paragraph_match_count': len(all_matches),
            'table_match_count': len(table_duplicates),
            'table_similarity': round(
                max((find_identical_tables(ta, tb)
                     for ta in tables_a for tb in tables_b), default=0.0) * 100, 1
            ),
            'matches': [
                {
                    'source_text': m.source.text[:100],
                    'target_text': m.target.text[:100],
                    'similarity': round(m.similarity, 3),
                    'type': m.match_type,
                }
                for m in sorted(all_matches, key=lambda x: x.similarity, reverse=True)[:20]
            ],
            'metadata_comparison': meta_comparison,
            **risk_assessment,
        }

        log.info(f"查重完成 | 相似度={result['overall_similarity']}% | "
                f"风险等级={risk_assessment['risk_level']}")
        return result

    @staticmethod
    def _merge_matches(matches: List[DuplicateMatch]) -> List[DuplicateMatch]:
        """合并去重匹配结果"""
        seen = set()
        unique = []
        for match in matches:
            key = (match.source.index, match.target.index)
            if key not in seen:
                seen.add(key)
                unique.append(match)
        return unique


def check_duplicates(file_paths: List[str],
                    mode: str = "通用",
                    threshold: float = 0.8,
                    output_path: str = None) -> Dict:
    """多文件批量查重的便捷函数

    Args:
        file_paths: 文件路径列表（2个或以上）
        mode: 查重模式
        threshold: 相似度阈值
        output_path: 报告输出路径（可选）

    Returns:
        完整查重报告
    """
    if len(file_paths) < 2:
        raise ValueError("至少需要2个文件进行查重")

    checker = DuplicateChecker(mode=mode, threshold=threshold)

    # 两两比对
    comparisons = []
    overall_max_sim = 0.0

    for i in range(len(file_paths)):
        for j in range(i + 1, len(file_paths)):
            result = checker.check_pair(file_paths[i], file_paths[j])
            comparisons.append(result)
            overall_max_sim = max(overall_max_sim, result.get('overall_similarity', 0))

    # 汇总报告
    from .report import generate_summary_text

    report = {
        'mode': mode,
        'file_count': len(file_paths),
        'comparison_count': len(comparisons),
        'overall_max_similarity': overall_max_sim,
        'comparisons': comparisons,
        'risk_level': max(
            (c.get('risk_level', '安全') for c in comparisons),
            key=lambda x: {'高风险': 4, '中等风险': 3, '低风险': 2, '安全': 1}.get(x, 0),
        ),
        'risk_summary': generate_summary_text({
            'mode': mode,
            'overall_max_similarity': overall_max_sim,
        }),
        'generated_at': __import__('datetime').datetime.now().isoformat(),
    }

    # 保存报告
    if output_path:
        from .report import save_report
        saved_path = save_report(report, output_path)
        report['saved_to'] = saved_path

    return report
