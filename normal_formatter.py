"""NormalFormatter — 标准格式化引擎 v7.0。

通过组合多个 mixin 实现，每个 mixin 负责一类职责。
所有方法的具体实现见 mixins/ 下对应模块。

继承顺序（MRO）：
    PageSetupMixin → ContentMixin → TablesMixin → PageElementsMixin → PersistenceMixin → FormatterInterface
"""
from docx import Document

from interface import FormatterInterface
from constants import safe_heading_font, safe_body_font
from mixins import (
    PageSetupMixin,
    ContentMixin,
    TablesMixin,
    PageElementsMixin,
    PersistenceMixin,
)


class NormalFormatter(
    PageSetupMixin,
    ContentMixin,
    TablesMixin,
    PageElementsMixin,
    PersistenceMixin,
    FormatterInterface,
):
    """标准格式（技术标/商务标通用）v7.0。

    特性：
    - 分节符支持 (add_section_break)
    - 三线表样式 (add_professional_table)
    - 奇偶页不同页眉页脚
    - 分隔线和注意事项框
    - 自动分页（h1前/h2可配置）
    """

    def __init__(
        self,
        doc=None,
        heading_font: str | None = None,
        body_font: str | None = None,
        page_break_before_h2: bool = False,
        project_name: str = '',
    ):
        """初始化格式化引擎。

        Args:
            doc: Document 对象（复用时传入）
            heading_font: 标题字体
            body_font: 正文字体
            page_break_before_h2: 二级标题前是否插入分页符（默认False）
            project_name: 项目名称（用于偶数页页眉）
        """
        self.heading_font = safe_heading_font(heading_font)
        self.body_font = safe_body_font(body_font)
        self.page_break_before_h2 = page_break_before_h2
        self.project_name = project_name
        self._current_chapter = ''  # 当前章节名称（用于奇数页页眉）
        self._h1_count = 0  # 已渲染的一级标题计数

        if doc is None:
            self.doc = Document()
            self._init_styles()
        else:
            self.doc = doc
            self._apply_fonts()
        self._setup_page()
