"""
标书检查执行引擎
协调执行各类检查规则并汇总结果
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .rules import (
    CheckRule,
    RULE_REGISTRY,
    get_rules_by_category,
    get_rules_by_severity,
)

log = logging.getLogger(__name__)


class CheckResult:
    """单条检查结果"""

    def __init__(self, rule: CheckRule, passed: bool,
                 message: str = '', details: Dict = None):
        self.rule = rule
        self.passed = passed
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()

    @property
    def is_critical(self) -> bool:
        return self.rule.severity == 'critical'

    def to_dict(self) -> Dict:
        return {
            'rule_id': self.rule.rule_id,
            'rule_name': self.rule.name,
            'category': self.rule.category,
            'severity': self.rule.severity,
            'passed': self.passed,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
        }


class BidChecker:
    """标书检查引擎 v2.0

    功能：
    - 执行预定义检查规则集
    - 支持按类别/严重级别筛选规则
    - 汇总检查结果并生成报告
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 检查配置（可选）
                - include_rules: 包含的规则ID列表
                - exclude_rules: 排除的规则ID列表
                - severity_threshold: 最低严重级别
        """
        self.config = config or {}
        self.results: List[CheckResult] = []

        # 统计信息
        self.stats = {
            'total_rules': 0,
            'passed': 0,
            'failed': 0,
            'critical_failed': 0,
            'by_category': {},
            'by_severity': {},
        }

        log.info("BidChecker初始化完成")

    def _get_active_rules(self) -> List[CheckRule]:
        """获取当前激活的规则列表"""
        rules = list(RULE_REGISTRY.values())

        # 应用过滤配置
        include = self.config.get('include_rules')
        if include:
            rules = [r for r in rules if r.rule_id in include]

        exclude = self.config.get('exclude_rules')
        if exclude:
            rules = [r for r in rules if r.rule_id not in exclude]

        # 严重级别阈值
        threshold = self.config.get('severity_threshold', 'info')
        severity_order = {'critical': 4, 'warning': 3, 'info': 2}
        min_level = severity_order.get(threshold, 1)
        rules = [r for r in rules if severity_order.get(r.severity, 0) >= min_level]

        return rules

    def check(self, context: Dict[str, Any]) -> List[CheckResult]:
        """执行完整检查

        Args:
            context: 检查上下文
                - text: 文档文本内容
                - docx_path: Word文档路径（可选）
                - required_clauses: 必响应条款列表
                - score_items: 评分项列表
                - tables: 表格数据列表

        Returns:
            检查结果列表
        """
        log.info("开始执行标书检查")
        self.results = []
        active_rules = self._get_active_rules()
        self.stats['total_rules'] = len(active_rules)

        for rule in active_rules:
            log.debug(f"执行规则: {rule.rule_id} - {rule.name}")
            result_data = rule.execute(context)

            check_result = CheckResult(
                rule=rule,
                passed=result_data.get('passed', False),
                message=result_data.get('message', ''),
                details=result_data.get('details', {}),
            )

            self.results.append(check_result)

            # 更新统计
            if check_result.passed:
                self.stats['passed'] += 1
            else:
                self.stats['failed'] += 1
                if check_result.is_critical:
                    self.stats['critical_failed'] += 1

            # 分类统计
            cat = rule.category
            sev = rule.severity
            self.stats['by_category'][cat] = self.stats['by_category'].get(cat, 0) + 1
            self.stats['by_severity'][sev] = self.stats['by_severity'].get(sev, 0) + 1

        log.info(f"检查完成 | 总计{len(active_rules)}项 "
                f"| 通过{self.stats['passed']} | 失败{self.stats['failed']}"
                f"| 严重失败{self.stats['critical_failed']}")

        return self.results

    def get_critical_issues(self) -> List[CheckResult]:
        """获取所有关键问题（未通过的critical级）"""
        return [r for r in self.results
                if not r.passed and r.is_critical]

    def get_all_issues(self) -> List[CheckResult]:
        """获取所有未通过的问题"""
        return [r for r in self.results if not r.passed]

    def get_summary(self) -> Dict[str, Any]:
        """获取检查结果摘要

        Returns:
            摘要字典，包含通过率、问题统计等
        """
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            'total_rules': total,
            'passed': passed,
            'failed': total - passed,
            'pass_rate': round(pass_rate, 1),
            'critical_issues': len(self.get_critical_issues()),
            'all_issues': len(self.get_all_issues()),
            'has_critical_failure': self.stats['critical_failed'] > 0,
            'can_submit': self.stats['critical_failed'] == 0,
            **self.stats,
        }

    def to_report_dict(self) -> Dict[str, Any]:
        """转换为可序列化的报告字典"""
        summary = self.get_summary()

        return {
            'check_time': datetime.now().isoformat(),
            'summary': summary,
            'issues': [r.to_dict() for r in self.get_all_issues()],
            'critical_issues': [r.to_dict() for r in self.get_critical_issues()],
            'passed_checks': [r.to_dict() for r in self.results if r.passed],
        }
