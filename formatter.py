"""Formatter 聚合模块 — v8.1 创建

原 bid_core/formatter/ 包的扁平化聚合。
统一导出 NormalFormatter/PremiumFormatter/DarkFormatter + 字体常量，
使 `from formatter import NormalFormatter` 和 `from bid_core.formatter import NormalFormatter` 均可工作。
"""
from normal_formatter import NormalFormatter
from premium_formatter import PremiumFormatter
from dark_formatter import DarkFormatter
from constants import safe_heading_font, safe_body_font, HEADING_FONTS, BODY_FONTS
from interface import FormatterInterface

__all__ = [
    'NormalFormatter',
    'PremiumFormatter',
    'DarkFormatter',
    'FormatterInterface',
    'safe_heading_font',
    'safe_body_font',
    'HEADING_FONTS',
    'BODY_FONTS',
]
