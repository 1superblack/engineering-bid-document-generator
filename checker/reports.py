"""
标书检查报告生成模块
生成格式化的检查结果报告
"""
import json
from typing import Dict, Any
from datetime import datetime

from log_helper import get_logger
log = get_logger(__name__)


def generate_text_report(check_result: Dict[str, Any]) -> str:
    """生成文本格式报告

    Args:
        check_result: 检查结果字典（来自executor的to_report_dict方法）

    Returns:
        格式化的文本报告
    """
    lines = []
    lines.append("=" * 60)
    lines.append("标书检查报告")
    lines.append(f"生成时间: {check_result.get('check_time', '')}")
    lines.append("=" * 60)

    summary = check_result.get('summary', {})
    if summary:
        lines.append("")
        lines.append("📊 检查概要")
        lines.append(f"   总检查项: {summary.get('total_rules', 0)}")
        lines.append(f"   通过: {summary.get('passed', 0)}")
        lines.append(f"   失败: {summary.get('failed', 0)}")
        lines.append(f"   通过率: {summary.get('pass_rate', 0)}%")
        lines.append(f"   关键问题: {summary.get('critical_issues', 0)}")
        lines.append(f"   可提交: {'是' if summary.get('can_submit') else '否'}")

    # 关键问题
    critical = check_result.get('critical_issues', [])
    if critical:
        lines.append("")
        lines.append("⚠️  关键问题（必须修复）")
        for issue in critical[:10]:  # 限制显示数量
            name = issue.get('rule_name', '未知')
            msg = issue.get('message', '')
            lines.append(f"   ❌ [{issue.get('rule_id')}] {name}: {msg}")

    # 所有问题
    all_issues = check_result.get('issues', [])
    if all_issues and len(all_issues) > len(critical):
        lines.append("")
        lines.append("📋 其他问题")
        # 只显示非关键问题
        other_issues = [i for i in all_issues
                       if i.get('severity') != 'critical']
        for issue in other_issues[:15]:
            sev_icon = '⚠️' if issue.get('severity') == 'warning' else 'ℹ️'
            lines.append(f"   {sev_icon} [{issue.get('rule_id')}] "
                        f"{issue.get('rule_name', '')}: {issue.get('message', '')}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def generate_json_report(check_result: Dict[str, Any],
                        pretty: bool = True) -> str:
    """生成JSON格式报告

    Args:
        check_result: 检查结果字典
        pretty: 是否美化输出

    Returns:
        JSON字符串
    """
    indent = 2 if pretty else None
    return json.dumps(check_result, ensure_ascii=False, indent=indent, default=str)


def generate_markdown_report(check_result: Dict[str, Any]) -> str:
    """生成Markdown格式报告

    Args:
        check_result: 检查结果字典

    Returns:
        Markdown文本
    """
    md_lines = ["# 标书检查报告", ""]
    md_lines.append(f"> 检查时间: {check_result.get('check_time', '')}")
    md_lines.append("")

    summary = check_result.get('summary', {})
    if summary:
        md_lines.append("## 📊 检查概要")
        md_lines.append("")
        md_lines.append("| 项目 | 数值 |")
        md_lines.append("|------|------|")
        md_lines.append(f"| 总检查项 | {summary.get('total_rules', 0)} |")
        md_lines.append(f"| 通过 | ✅ {summary.get('passed', 0)} |")
        md_lines.append(f"| 失败 | ❌ {summary.get('failed', 0)} |")
        md_lines.append(f"| 通过率 | **{summary.get('pass_rate', 0)}%** |")
        md_lines.append("")

    critical = check_result.get('critical_issues', [])
    if critical:
        md_lines.append("## ⚠️ 关键问题")
        md_lines.append("")
        md_lines.append("| 规则ID | 名称 | 描述 |")
        md_lines.append("|--------|------|------|")
        for issue in critical:
            md_lines.append(f"| {issue.get('rule_id', '')} "
                          f"| {issue.get('rule_name', '')} "
                          f"| {issue.get('message', '')} |")
        md_lines.append("")

    return "\n".join(md_lines)


def save_report(check_result: Dict[str, Any],
               output_path: str,
               format_type: str = 'json') -> str:
    """保存报告到文件

    Args:
        check_result: 检查结果
        output_path: 输出路径
        format_type: 输出格式 (json/text/markdown)

    Returns:
        保存的文件路径
    """
    generators = {
        'json': lambda r: generate_json_report(r),
        'text': lambda r: generate_text_report(r),
        'markdown': lambda r: generate_markdown_report(r),
    }

    generator = generators.get(format_type)
    if not generator:
        raise ValueError(f"不支持的报告格式: {format_type}")

    content = generator(check_result)

    ext_map = {'json': '.json', 'text': '.txt', 'markdown': '.md'}
    if not output_path.endswith(tuple(ext_map.values())):
        output_path += ext_map.get(format_type, '')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_path


def print_summary_to_console(check_result: Dict[str, Any]) -> None:
    """将摘要打印到控制台"""
    report = generate_text_report(check_result)
    print(report)
