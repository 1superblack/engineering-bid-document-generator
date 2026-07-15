"""
查重报告生成模块
生成格式化的查重结果报告
"""
import json
from typing import Dict
from datetime import datetime

from log_helper import get_logger
log = get_logger(__name__)


def print_report(report: Dict) -> None:
    """打印格式化的查重报告

    Args:
        report: 查重结果字典
    """
    print("\n" + "=" * 60)
    print("📋 文档查重报告")
    print("=" * 60)

    # 错误检查
    if report.get('error'):
        print(f"\n❌ 查重失败: {report.get('error', '未知错误')}")
        return

    # 基本信息
    print(f"\n📊 基本信息")
    print(f"   查重模式: {report.get('mode', '通用')}")
    print(f"   文件数量: {report.get('file_count', 0)}")
    print(f"   比对组数: {report.get('comparison_count', 0)}")
    print(f"   最高相似度: {report.get('overall_max_similarity', 0):.1f}%")
    print(f"   风险等级: {report.get('risk_level', '未知')}")

    # 文档详情
    if 'documents' in report:
        print(f"\n📄 文档详情")
        for name, info in report['documents'].items():
            error_msg = info.get('error')
            if error_msg:
                print(f"   • {info.get('file', name)}: 解析失败 - {error_msg}")
            else:
                print(f"   • {info.get('file', name)}")
                print(f"     段落数: {info.get('paragraph_count', 0)} "
                      f"| 表格数: {info.get('table_count', 0)}")

    # 比对结果
    comparisons = report.get('comparisons', [])
    if comparisons:
        print(f"\n🔍 比对结果")
        for comp in comparisons:
            print(f"\n   {comp.get('doc_a')} vs {comp.get('doc_b')}")
            print(f"   ├─ 全文相似度: {comp.get('overall_similarity', 0):.1f}%")
            print(f"   ├─ 段落匹配: {comp.get('paragraph_match_count', 0)}处")
            print(f"   ├─ 表格匹配: {comp.get('table_match_count', 0)}处")
            print(f"   └─ 表格相似度: {comp.get('table_similarity', 0):.1f}%")

            # 元数据警告
            meta = comp.get('metadata_comparison', {})
            warnings = meta.get('warnings', [])
            if warnings:
                print(f"   ⚠️ 元数据警告:")
                for w in warnings:
                    print(f"      {w}")

            # 高重复段落
            high_matches = [m for m in comp.get('matches', [])
                           if m.get('similarity', 0) > 0.9]
            if high_matches:
                for match in high_matches[:5]:  # 只显示前5条
                    print(f"   {match}")

    # 风险摘要
    summary = report.get('risk_summary', '')
    if summary:
        print(f"\n💡 风险摘要")
        print(f"   {summary}")

    print("\n" + "=" * 60)


def generate_json_report(report: Dict, pretty: bool = True) -> str:
    """生成JSON格式报告

    Args:
        report: 查重结果字典
        pretty: 是否美化输出

    Returns:
        JSON字符串
    """
    indent = 2 if pretty else None
    return json.dumps(report, ensure_ascii=False, indent=indent)


def save_report(report: Dict, output_path: str,
                format_type: str = 'json') -> str:
    """保存报告到文件

    Args:
        report: 查重结果字典
        output_path: 输出路径
        format_type: 输出格式（json/text）

    Returns:
        保存的文件路径
    """
    try:
        if format_type == 'json':
            content = generate_json_report(report)
            if not output_path.endswith('.json'):
                output_path += '.json'
        else:
            from io import StringIO
            import sys

            old_stdout = sys.stdout
            sys.stdout = StringIO()
            print_report(report)
            content = sys.stdout.getvalue()
            sys.stdout = old_stdout

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path

    except Exception as e:
        raise IOError(f"保存报告失败: {e}")


def generate_summary_text(report: Dict) -> str:
    """生成简短的文本摘要

    Args:
        report: 查重结果

    Returns:
        文本摘要
    """
    lines = [
        f"文档查重完成 - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"模式: {report.get('mode', '通用')}",
        f"文件数: {report.get('file_count', 0)}",
        f"最高相似度: {report.get('overall_max_similarity', 0):.1f}%",
        f"风险等级: {report.get('risk_level', '未知')}",
    ]

    risk_summary = report.get('risk_summary', '')
    if risk_summary:
        lines.append(f"\n{risk_summary}")

    return '\n'.join(lines)
