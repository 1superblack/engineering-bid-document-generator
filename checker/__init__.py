"""
标书检查模块 v2.0
对标书进行格式、内容、完整性检查

模块结构:
- rules: 检查规则定义（FormatRules/ContentRules/CompletenessRules）
- executor: 执行引擎（BidChecker类）
- reports: 报告生成（文本/JSON/Markdown）
"""

from .executor import BidChecker, CheckResult
from .rules import (
    CheckRule,
    FormatRules,
    ContentRules,
    CompletenessRules,
    RULE_REGISTRY,
    get_rules_by_category,
    get_rules_by_severity,
)
from .reports import (
    generate_text_report,
    generate_json_report,
    generate_markdown_report,
    save_report,
    print_summary_to_console,
)
from .risk_grading import grade_risk, render_risk_markdown

__all__ = [
    # 主接口
    'BidChecker',
    'CheckResult',
    # 规则
    'CheckRule',
    'FormatRules',
    'ContentRules',
    'CompletenessRules',
    'RULE_REGISTRY',
    # 辅助函数
    'get_rules_by_category',
    'get_rules_by_severity',
    # 报告
    'generate_text_report',
    'generate_json_report',
    'generate_markdown_report',
    'save_report',
    'print_summary_to_console',
    # P2 风险分级
    'grade_risk',
    'render_risk_markdown',
]

__version__ = '2.0.0'
