"""PageSetupMixin — 页面参数、样式初始化、列宽计算、分页分节控制。

拆分自原 formatter.py v7.0 NormalFormatter。
"""
from docx.shared import Cm, Pt, RGBColor
from docx.oxml.ns import qn
from docx.enum.section import WD_SECTION


class PageSetupMixin:
    """页面设置与文档初始化相关方法。"""

    # 宽表格列数阈值：超过此值启用自动列宽适配
    WIDE_TABLE_THRESHOLD: int = 8

    def _setup_page(self) -> None:
        """设置页面参数：A4纸、页边距、页眉页脚距离。

        v7.1: 页边距统一为标书规范值(上2.5/下2.5/左2.8/右2.6)
        """
        for section in self.doc.sections:
            section.page_width = Cm(21.0)
            section.page_height = Cm(29.7)
            section.top_margin = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin = Cm(2.8)
            section.right_margin = Cm(2.6)
            section.header_distance = Cm(1.5)
            section.footer_distance = Cm(1.75)

    def _init_styles(self) -> None:
        """初始化样式。"""
        s = self.doc.styles['Normal']
        s.font.name = self.body_font
        s.font.size = Pt(12)
        s.font.color.rgb = RGBColor(0, 0, 0)
        s._element.rPr.rFonts.set(qn('w:eastAsia'), self.body_font)
        pf = s.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(3)
        pf.line_spacing = Pt(28)

    def _apply_fonts(self) -> None:
        """应用字体到 Normal 样式（复用 Document 场景）。"""
        try:
            s = self.doc.styles['Normal']
            s.font.name = self.body_font
            s._element.rPr.rFonts.set(qn('w:eastAsia'), self.body_font)
        except Exception as e:
            from bid_core.logger import get_logger
            get_logger(__name__).debug('Normal 样式字体设置失败: %s', e)

    def _get_available_table_width(self):
        """获取可用表格宽度（页面宽度减去左右边距）。"""
        for section in self.doc.sections:
            page_w = section.page_width
            left_m = section.left_margin
            right_m = section.right_margin
            if page_w and left_m and right_m:
                return page_w - left_m - right_m
        return Cm(15.6)  # 默认A4：21cm - 2.8cm - 2.6cm = 15.6cm

    def _calc_column_widths(self, num_cols: int):
        """计算列宽 — 自动适配列数。

        策略：
        - 少于 WIDE_TABLE_THRESHOLD 列：均分，12pt
        - 8-10 列：缩放字体到 11pt，均分宽度
        - 11-15 列：缩放字体到 10pt，均分宽度
        - 16+ 列：缩放字体到 9pt，均分宽度

        Returns:
            (column_widths, font_size) 元组
        """
        total_width = self._get_available_table_width()

        if num_cols < self.WIDE_TABLE_THRESHOLD:
            col_w = total_width / num_cols
            return [col_w] * num_cols, Pt(12)
        elif num_cols <= 10:
            col_w = total_width / num_cols
            return [col_w] * num_cols, Pt(11)
        elif num_cols <= 15:
            col_w = total_width / num_cols
            return [col_w] * num_cols, Pt(10)
        else:
            col_w = total_width / num_cols
            return [col_w] * num_cols, Pt(9)

    # ── 分页 / 分节 ──

    def add_page_break(self) -> None:
        """强制分页符 — v7.0 统一命名（兼容旧 page_break）。"""
        self.doc.add_page_break()

    def add_section_break(self, start_type: str = 'odd_page'):
        """分节符 — v7.0 新增。

        Args:
            start_type: 起始方式
                'odd_page' - 奇数页开始（默认，标书章节常用）
                'new_page' - 新页开始
                'even_page' - 偶数页开始
                'continuous' - 连续（不分页）
        """
        type_map = {
            'odd_page': WD_SECTION.ODD_PAGE,
            'new_page': WD_SECTION.NEW_PAGE,
            'even_page': WD_SECTION.EVEN_PAGE,
            'continuous': WD_SECTION.CONTINUOUS,
        }
        section_type = type_map.get(start_type, WD_SECTION.ODD_PAGE)
        new_section = self.doc.add_section(section_type)
        # 继承页面设置（v7.1: 标书规范值）
        new_section.page_width = Cm(21.0)
        new_section.page_height = Cm(29.7)
        new_section.top_margin = Cm(2.5)
        new_section.bottom_margin = Cm(2.5)
        new_section.left_margin = Cm(2.8)
        new_section.right_margin = Cm(2.6)
        new_section.header_distance = Cm(1.5)
        new_section.footer_distance = Cm(1.75)
        return new_section

    def page_break(self) -> None:
        """分页符（兼容旧接口）。"""
        self.doc.add_page_break()
