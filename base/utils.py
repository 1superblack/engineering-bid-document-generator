"""
富内容引擎 - 基础工具模块
包含模板轮转、通用工具函数等
"""
import random
import logging
from typing import Any

log = logging.getLogger(__name__)

# 全局状态（用于跨请求的多样性）
_global_state = {
    'rotation': {},  # pool_name -> current_index
}


def _rotate(pool_name: str, size: int) -> int:
    """从池中按轮询选择索引

    Args:
        pool_name: 池名称
        size: 池大小

    Returns:
        当前选择的索引（0到size-1）
    """
    if size <= 0:
        return 0

    current = _global_state['rotation'].get(pool_name, 0)
    idx = current % size
    _global_state['rotation'][pool_name] = current + 1

    return idx


def reset_rotation() -> None:
    """重置所有轮询状态"""
    _global_state['rotation'].clear()
    log.debug("已重置模板轮询状态")


def get_current_rotation() -> dict:
    """获取当前轮询状态（用于调试）"""
    return dict(_global_state['rotation'])


def format_number(value: Any, decimal_places: int = 2) -> str:
    """格式化数字显示

    Args:
        value: 数值
        decimal_places: 小数位数

    Returns:
        格式化后的字符串
    """
    try:
        num = float(value)
        if num == int(num):
            return str(int(num))
        return f"{num:.{decimal_places}f}"
    except (ValueError, TypeError):
        return str(value)


def safe_truncate(text: str, max_length: int = 100,
                  suffix: str = '...') -> str:
    """安全截断文本

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, top_k: int = 5) -> list:
    """简单关键词提取（基于词频）

    Args:
        text: 输入文本
        top_k: 返回前k个关键词

    Returns:
        关键词列表
    """
    import re
    from collections import Counter

    # 简单分词（按字符或词汇边界）
    words = re.findall(r'[\u4e00-\u9fff]{2,}', text)

    # 过滤停用词
    stopwords = {'我们', '进行', '通过', '采用', '实现', '确保', '加强'}
    words = [w for w in words if w not in stopwords]

    # 返回高频词
    counter = Counter(words)
    return [word for word, _ in counter.most_common(top_k)]
