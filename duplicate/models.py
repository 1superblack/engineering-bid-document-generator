"""
查重数据模型
定义段落、表格、匹配结果等数据结构
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set

from log_helper import get_logger
log = get_logger(__name__)


@dataclass
class Paragraph:
    """文档段落"""
    text: str
    index: int = 0
    page_num: int = 0

    def __hash__(self):
        return hash(self.text)


@dataclass
class TableData:
    """表格数据"""
    rows: List[List[str]] = field(default_factory=list)
    caption: str = ''
    page_num: int = 0

    def to_text(self) -> str:
        """转换为文本表示"""
        lines = []
        if self.caption:
            lines.append(f"表: {self.caption}")
        for row in self.rows:
            lines.append(" | ".join(row))
        return "\n".join(lines)

    def __hash__(self):
        return hash(self.to_text())


@dataclass
class DuplicateMatch:
    """重复匹配结果"""
    source: Paragraph  # 源段落
    target: Paragraph  # 目标段落
    similarity: float  # 相似度 (0-1)
    match_type: str = 'text'  # 'text' | 'table' | 'semantic'
    position_a: int = 0
    position_b: int = 0


@dataclass
class MetadataInfo:
    """文档元数据"""
    file_path: str = ''
    author: str = ''
    company: str = ''
    created_date: str = ''
    modified_date: str = ''
    title: str = ''

    def to_dict(self) -> Dict:
        return {
            'file': self.file_path,
            'author': self.author,
            'company': self.company,
            'created': self.created_date,
            'modified': self.modified_date,
            'title': self.title,
        }
