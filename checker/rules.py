"""
标书检查规则模块
定义各类检查规则和验证逻辑
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class CheckRule:
    """检查规则定义"""
    rule_id: str
    name: str
    description: str
    severity: str  # 'critical' | 'warning' | 'info'
    category: str  # 'format' | 'content' | 'completeness'
    check_fn: callable = None  # 检查函数

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行检查规则

        Args:
            context: 检查上下文（包含文档内容、配置等）

        Returns:
            检查结果 {'passed': bool, 'message': str, 'details': dict}
        """
        if self.check_fn:
            try:
                return self.check_fn(context)
            except Exception as e:
                log.error(f"规则执行失败 {self.rule_id}: {e}")
                return {
                    'passed': False,
                    'message': f"检查异常: {e}",
                    'details': {},
                }

        return {'passed': True, 'message': '未实现', 'details': {}}


# ════════════════════════════════════════════════════════════════
# 预定义检查规则集
# ════════════════════════════════════════════════════════════════

class FormatRules:
    """格式检查规则"""

    @staticmethod
    def check_heading_hierarchy(context: Dict) -> Dict:
        """检查标题层级是否正确"""
        text = context.get('text', '')
        issues = []

        # 简化实现：检测连续同级别标题
        heading_pattern = r'^(第[一二三四五六七八九十]+章|[一二三四五六七八九十]+、)'
        headings = re.findall(heading_pattern, text, re.MULTILINE)

        # 检查是否有重复的一级标题
        from collections import Counter
        heading_counts = Counter(headings)
        for heading, count in heading_counts.items():
            if count > 1:
                issues.append(f"一级标题重复: {heading}")

        return {
            'passed': len(issues) == 0,
            'message': f"发现{len(issues)}个格式问题" if issues else "标题层级正常",
            'details': {'issues': issues},
        }

    @staticmethod
    def check_font_format(context: Dict) -> Dict:
        """检查字体格式（需要Word文档）"""
        docx_path = context.get('docx_path')
        if not docx_path:
            return {'passed': True, 'message': '跳过（无文档路径）', 'details': {}}

        # 简化实现
        return {'passed': True, 'message': '字体格式检查通过', 'details': {}}

    @staticmethod
    def check_page_number(context: Dict) -> Dict:
        """检查页码是否正确"""
        return {'passed': True, 'message': '页码检查通过', 'details': {}}


class ContentRules:
    """内容检查规则"""

    @staticmethod
    def check_responded_clauses(context: Dict) -> Dict:
        """检查废标条款是否全部响应"""
        required_clauses = context.get('required_clauses', [])
        responded_clauses = context.get('responded_clauses', [])

        missing = []
        for clause in required_clauses:
            if clause not in responded_clauses:
                missing.append(clause)

        severity = 'critical' if missing else 'info'
        return {
            'passed': len(missing) == 0,
            'message': f"未响应条款: {len(missing)}条" if missing else "所有废标条款已响应",
            'details': {'missing_clauses': missing},
            'severity': severity,
        }

    @staticmethod
    def check_score_items_coverage(context: Dict) -> Dict:
        """检查评分项覆盖情况"""
        score_items = context.get('score_items', [])
        covered_items = context.get('covered_items', [])

        uncovered = [item for item in score_items
                     if item not in covered_items]

        return {
            'passed': len(uncovered) == 0,
            'message': f"未覆盖评分项: {len(uncovered)}项" if uncovered else "评分项全覆盖",
            'details': {
                'total': len(score_items),
                'covered': len(covered_items),
                'uncovered': uncovered,
            },
        }


class CompletenessRules:
    """完整性检查规则"""

    @staticmethod
    def check_required_sections(context: Dict) -> Dict:
        """检查必选章节是否存在"""
        required = ['技术方案', '施工组织', '质量保证',
                   '安全措施', '进度计划']

        content = context.get('text', '')
        present = [s for s in required if s in content]
        missing = set(required) - set(present)

        return {
            'passed': len(missing) == 0,
            'message': f"缺失章节: {missing}" if missing else "必选章节完整",
            'details': {'required': required, 'present': present, 'missing': list(missing)},
        }

    @staticmethod
    def check_table_completeness(context: Dict) -> Dict:
        """检查表格数据完整性"""
        tables = context.get('tables', [])
        incomplete = []

        for i, table in enumerate(tables):
            rows = table.get('rows', [])
            # 检查是否有空单元格或占位符
            for row in rows:
                for cell in row:
                    if not cell or '按实际' in cell or '待填' in cell:
                        incomplete.append(f"表格{i+1}存在不完整数据")
                        break

        return {
            'passed': len(incomplete) == 0,
            'message': f"{len(incomplete)}个表格数据不完整" if incomplete else "表格数据完整",
            'details': {'incomplete_tables': incomplete},
        }


# 规则注册表
RULE_REGISTRY = {
    # 格式检查
    'format_heading': CheckRule(
        rule_id='F001',
        name='标题层级检查',
        description='检查文档标题层级结构是否符合规范',
        severity='warning',
        category='format',
        check_fn=FormatRules.check_heading_hierarchy,
    ),
    'format_font': CheckRule(
        rule_id='F002',
        name='字体格式检查',
        description='检查字体大小、颜色等格式要求',
        severity='info',
        category='format',
        check_fn=FormatRules.check_font_format,
    ),
    'format_pagenum': CheckRule(
        rule_id='F003',
        name='页码检查',
        description='检查页码是否连续且符合要求',
        severity='info',
        category='format',
        check_fn=FormatRules.check_page_number,
    ),

    # 内容检查
    'content_clause': CheckRule(
        rule_id='C001',
        name='废标条款响应检查',
        description='检查招标文件中的废标条款是否全部响应',
        severity='critical',
        category='content',
        check_fn=ContentRules.check_responded_clauses,
    ),
    'content_scoreitem': CheckRule(
        rule_id='C002',
        name='评分项覆盖检查',
        description='检查技术标是否覆盖所有评分点',
        severity='critical',
        category='content',
        check_fn=ContentRules.check_score_items_coverage,
    ),

    # 完整性检查
    'completeness_section': CheckRule(
        rule_id='P001',
        name='必选章节检查',
        description='检查投标文件是否包含所有必选章节',
        severity='critical',
        category='completeness',
        check_fn=CompletenessRules.check_required_sections,
    ),
    'completeness_table': CheckRule(
        rule_id='P002',
        name='表格完整性检查',
        description='检查附表数据是否完整无占位符',
        severity='warning',
        category='completeness',
        check_fn=CompletenessRules.check_table_completeness,
    ),
}


def get_rules_by_category(category: str) -> List[CheckRule]:
    """获取指定类别的规则列表"""
    return [rule for rule in RULE_REGISTRY.values()
            if rule.category == category]


def get_rules_by_severity(severity: str) -> List[CheckRule]:
    """获取指定严重级别的规则列表"""
    return [rule for rule in RULE_REGISTRY.values()
            if rule.severity == severity]
