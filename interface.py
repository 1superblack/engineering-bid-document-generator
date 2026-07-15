"""FormatterInterface — 格式化引擎抽象接口。

拆分自原 formatter.py v7.0。
所有 Formatter 实现类必须实现此接口，确保 bid_core 上层调用稳定。
"""
from abc import ABC, abstractmethod
from typing import Any


class FormatterInterface(ABC):
    """格式化引擎接口 — 定义上层调用契约。"""

    @abstractmethod
    def h1(self, index: int, title: str) -> None:
        """一级标题（一、二、三）"""
        raise NotImplementedError

    @abstractmethod
    def h2(self, title: str) -> None:
        """二级标题（（一）（二）（三））"""
        raise NotImplementedError

    @abstractmethod
    def h3(self, title: str) -> None:
        """三级标题（1、2、3 或 1.1 1.2）"""
        raise NotImplementedError

    @abstractmethod
    def body(self, *args: Any) -> None:
        """正文段落（支持可变参数自动拼接）"""
        raise NotImplementedError

    @abstractmethod
    def body_list(self, items: list[str]) -> None:
        """正文列表（每项输出为带序号段落）"""
        raise NotImplementedError

    @abstractmethod
    def body_bold(self, text: str) -> None:
        """加粗正文"""
        raise NotImplementedError

    @abstractmethod
    def table(self, headers: list[str], rows: list[list[Any]]) -> None:
        """标准表格"""
        raise NotImplementedError

    @abstractmethod
    def page_break(self) -> None:
        """分页符"""
        raise NotImplementedError

    @abstractmethod
    def add_heading(self, text: str) -> None:
        """附表标题"""
        raise NotImplementedError

    @abstractmethod
    def save(self, path: str) -> None:
        """保存文档"""
        raise NotImplementedError

    @abstractmethod
    def get_document(self):
        """获取底层 Document 对象（用于合并）"""
        raise NotImplementedError
