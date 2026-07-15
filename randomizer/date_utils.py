"""
日期工具函数 v6.0

为施工计划生成随机但合理的日期范围。
"""

import random
import re
import datetime
from typing import Optional, Tuple

from log_helper import get_logger
log = get_logger(__name__)


def generate_date_range(
    start_date: Optional[str] = None,
    duration_days: int = 90,
    variance_days: int = 7
) -> Tuple[str, str]:
    """
    生成合理的日期范围

    Args:
        start_date: 起始日期字符串（如 "2025-06-01"），None则使用今天
        duration_days: 工期天数（默认90天）
        variance_days: 起止日期的随机偏移范围（±7天）

    Returns:
        (开始日期, 结束日期) 元组，格式为 "YYYY年MM月DD日"
    """
    if start_date:
        start = _parse_date(start_date)
    else:
        start = datetime.date.today()

    # 随机偏移起始日期（±variance_days）
    offset_start = random.randint(-variance_days, variance_days)
    actual_start = start + datetime.timedelta(days=offset_start)

    # 工期也加入小幅随机波动（±5%）
    actual_duration = int(duration_days * (1 + random.uniform(-0.05, 0.05)))
    actual_end = actual_start + datetime.timedelta(days=actual_duration)

    return (
        _format_date(actual_start),
        _format_date(actual_end)
    )


def _parse_date(date_str: str) -> datetime.date:
    """解析多种格式的日期字符串"""
    formats = [
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%Y年%m月%d日',
        '%Y.%m.%d',
    ]

    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    # 如果都失败，尝试简单分割
    parts = re.split(r'[-/.年月日]', date_str)
    if len(parts) >= 3:
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            return datetime.date(year, month, day)
        except (ValueError, IndexError):
            pass

    # 兜底：返回今天
    return datetime.date.today()


def _format_date(dt: datetime.date) -> str:
    """格式化日期为中文字符串"""
    return f'{dt.year}年{dt.month}月{dt.day}日'
