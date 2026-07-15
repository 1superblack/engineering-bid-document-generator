#!/usr/bin/env python3
"""
print() → logger 自动转换工具 v2.0 (正则版)

使用正则表达式替换 print() 调用为 logging 调用。
更稳定，不依赖AST API的版本差异。

转换规则:
  - print(f"[模块] 信息") → log.info("信息")
  - print(f"...失败...") → log.error("...")
  - print(f"...警告...") → log.warning("...")
  - 保留 __main__ 块中的print

用法:
    python tools/replace_prints.py [文件路径|目录] [--dry-run]
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict


# 匹配 print() 调用的正则模式
PRINT_PATTERN = re.compile(
    r'print\('                    # print(
    r'(f?["\'].*?["\'])'           # 第1组: 字符串参数（含f-string标记）
    r'([^)]*)?'                     # 第2组: 可选的其他参数（如file=sys.stderr）
    r'\)',                          # )
    re.DOTALL
)

# 模块名前缀模式（用于提取日志标签）
MODULE_TAG_PATTERN = re.compile(r'\[([\w_\.]+)\]\s*')


def determine_log_level(text: str) -> str:
    """
    根据文本内容推断日志级别

    Args:
        text: print语句中的文本内容

    Returns:
        'info', 'warning', 或 'error'
    """
    text_lower = text.lower()

    error_keywords = [
        '错误', '失败', '异常', 'error', 'exception', 'fail',
        '无法', '不存在', '无效', '中断', '崩溃'
    ]
    if any(kw in text_lower for kw in error_keywords):
        return 'error'

    warning_keywords = [
        '警告', 'warn', '忽略', '降级', '跳过', 'warning',
        '未找到', '缺失', '超时', '已禁用'
    ]
    if any(kw in text_lower for kw in warning_keywords):
        return 'warning'

    # 默认info
    return 'info'


def convert_fstring_to_log_format(text: str) -> Tuple[str, List[str]]:
    """
    将 f-string 文本转换为 logger 的 % 格式

    示例:
        f"值={x}, 结果={y}" → ("%s=%s, 结果=%s", ["x", "y"])
        "静态文本" → ("静态文本", [])
    """
    if not text.startswith('f') or not text.startswith(('f"', "f'")):
        # 普通字符串：移除前缀标签
        clean = MODULE_TAG_PATTERN.sub('', text).strip()
        return clean, []

    # 提取引号类型
    quote_char = text[1]
    content = text[2:-1]  # 去掉 f" 和 "

    # 解析f-string内容，将 {expr} 替换为 %s
    parts = []
    args = []
    current = []
    brace_depth = 0
    expr_start = None

    i = 0
    while i < len(content):
        char = content[i]

        if char == '{':
            if brace_depth == 0:
                # 保存之前的字面文本
                parts.append(''.join(current))
                current = []
                expr_start = i + 1
            brace_depth += 1
        elif char == '}':
            brace_depth -= 1
            if brace_depth == 0 and expr_start is not None:
                # 提取表达式
                expr = content[expr_start:i].strip()
                args.append(expr)
                parts.append('%s')
                expr_start = None
        else:
            if brace_depth == 0:
                current.append(char)
        i += 1

    if current:
        parts.append(''.join(current))

    format_str = ''.join(parts)
    # 移除模块标签前缀
    format_str = MODULE_TAG_PATTERN.sub('', format_str).strip()

    return format_str, args


def transform_print_line(line: str) -> str:
    """
    转换单行print调用为logger调用

    Args:
        line: 包含print()调用的代码行

    Returns:
        转换后的代码行，或原行（如果不匹配）
    """
    match = PRINT_PATTERN.search(line)
    if not match:
        return line

    raw_string = match.group(1)
    extra_args = match.group(2) or ''

    # 跳过特殊情况
    if 'file=' in extra_args and 'stderr' in extra_args:
        return line  # 保留 stderr 输出

    # 确定日志级别
    log_level = determine_log_level(raw_string)

    # 转换格式化字符串
    format_str, args = convert_fstring_to_log_format(raw_string)

    # 构建新的logger调用
    if args:
        # 有参数的情况
        args_str = ', '.join(args)
        new_call = f"log.{log_level}(\"{format_str}\", {args_str})"
    else:
        new_call = f"log.{log_level}(\"{format_str}\")"

    # 替换原始print调用
    new_line = line[:match.start()] + new_call + line[match.end():]

    return new_line


def is_in_main_block(lines: List[str], line_num: int) -> bool:
    """
    判断指定行是否在 if __name__ == '__main__': 块中

    使用简单的缩进和块检测逻辑
    """
    in_main = False
    main_indent = -1

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 检测 __main__ 块开始
        if re.match(r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:", stripped):
            in_main = True
            main_indent = len(line) - len(line.lstrip())
            continue

        if in_main:
            # 检测是否仍在 __main__ 块内（同级或更深缩进）
            if stripped and not stripped.startswith('#'):
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= main_indent and stripped:
                    # 块结束了（遇到同级或更浅的非空行）
                    in_main = False
                    main_indent = -1
                elif i == line_num:
                    return True

    return False


def add_logger_import(source: str, module_name: str) -> str:
    """
    在源文件顶部添加logger导入语句

    在文档字符串之后、第一个import之前插入
    """
    lines = source.split('\n')

    # 检查是否已有logger导入
    has_logger_import = any('get_logger' in line or 'import logging' in line for line in lines)
    if has_logger_import:
        return source

    logger_lines = [
        f"from bid_core.logger import get_logger",
        f"",
        f"log = get_logger('{module_name}')",
        f""
    ]

    # 找到插入位置
    insert_pos = 0
    docstring_ended = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 处理文档字符串
        if stripped.startswith(('"""', "'''")):
            # 单行文档字符串
            if stripped.count(stripped[0]) >= 3:
                insert_pos = i + 1
                break
            # 多行文档字符串开始
            if not docstring_ended:
                docstring_ended = True
                insert_pos = i + 1  # 先假设下一行结束
            else:
                # 多行文档字符串结束
                insert_pos = i + 1
                break
            continue

        # 遇到第一个import/From
        if (docstring_ended or insert_pos > 0) and stripped and not stripped.startswith('#'):
            if stripped.startswith(('import ', 'from ')):
                insert_pos = i
                break
            elif stripped:  # 其他非空非注释行
                insert_pos = i
                break

    # 插入导入
    for j, import_line in enumerate(logger_lines):
        lines.insert(insert_pos + j, import_line)

    return '\n'.join(lines)


def transform_file(filepath: Path, dry_run: bool = False) -> Dict:
    """
    转换单个文件

    Returns:
        统计结果字典
    """
    result = {
        'file': str(filepath),
        'total': 0,
        'converted': 0,
        'skipped': 0,
        'status': 'ok',
        'error': None
    }

    try:
        source = filepath.read_text(encoding='utf-8')
        lines = source.split('\n')

        new_lines = []
        converted_count = 0
        skipped_count = 0

        for line_num, line in enumerate(lines):
            # 检查是否是print调用
            if PRINT_PATTERN.search(line):
                # 检查是否在__main__块中
                if is_in_main_block(lines, line_num):
                    new_lines.append(line)
                    skipped_count += 1
                else:
                    # 执行转换
                    transformed = transform_print_line(line)
                    if transformed != line:
                        new_lines.append(transformed)
                        converted_count += 1
                    else:
                        new_lines.append(line)
                        skipped_count += 1
            else:
                new_lines.append(line)

        result['total'] = converted_count + skipped_count
        result['converted'] = converted_count
        result['skipped'] = skipped_count

        # 如果有转换，添加logger导入
        if converted_count > 0:
            new_source = '\n'.join(new_lines)
            new_source_with_import = add_logger_import(new_source, filepath.stem)

            if dry_run:
                print(f"[DRY-RUN] {filepath.name}: {converted_count} prints → logger "
                      f"(跳过 {skipped_count} in __main__)")
            else:
                filepath.write_text(new_source_with_import, encoding='utf-8')
                print(f"[OK] {filepath.name}: {converted_count} prints → logger")
        else:
            result['status'] = 'no_change'

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        print(f"[ERROR] {filepath.name}: {e}", file=sys.stderr)

    return result


def main():
    """主入口"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target_path = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    target = Path(target_path)

    if not target.exists():
        print(f"[ERROR] 路径不存在: {target}", file=sys.stderr)
        sys.exit(1)

    results = []

    if target.is_file():
        results.append(transform_file(target, dry_run))
    elif target.is_dir():
        py_files = sorted(target.glob('*.py'))
        # 排除测试文件和工具脚本
        py_files = [f for f in py_files
                   if not f.name.startswith(('test_', 'e2e_', '_'))
                   and f.name != 'replace_prints.py']
        results.extend([transform_file(f, dry_run) for f in py_files])
    else:
        print(f"[ERROR] 不支持的路径类型: {target}", file=sys.stderr)
        sys.exit(1)

    # 打印汇总
    total_converted = sum(r['converted'] for r in results)
    total_skipped = sum(r['skipped'] for r in results)
    errors = sum(1 for r in results if r['status'] == 'error')

    print("\n" + "=" * 60)
    print(f"转换完成!")
    print(f"  总计转换: {total_converted} 处")
    print(f"  跳过(__main__): {total_skipped} 处")
    print(f"  错误: {errors} 个文件")

    if errors:
        print("\n错误文件:")
        for r in results:
            if r['status'] == 'error':
                print(f"  ⚠ {r['file']}: {r['error']}")

    if dry_run:
        print("\n💡 提示: 这是试运行模式。去掉 --dry-run 参数以执行真实替换。")

    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
