"""Formatter mixins 聚合模块 — v8.1 创建

原 bid_core/formatter/mixins/ 包的扁平化聚合。
各 mixin 定义在根目录的独立模块中，本模块统一重新导出，
使 normal_formatter.py 的 `from mixins import ...` 在扁平化结构下正常工作。
"""
from page_setup import PageSetupMixin
from content import ContentMixin
from tables import TablesMixin
from page_elements import PageElementsMixin
from persistence import PersistenceMixin

__all__ = [
    'PageSetupMixin',
    'ContentMixin',
    'TablesMixin',
    'PageElementsMixin',
    'PersistenceMixin',
]
