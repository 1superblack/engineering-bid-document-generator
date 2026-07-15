"""OOXML 元素操作辅助函数。

拆分自原 formatter.py v7.0。
集中管理底层 XML 元素创建，避免业务方法被 OOXML 细节淹没。
"""
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def make_border_element(
    tag: str,
    val: str = 'single',
    sz: str = '4',
    space: str = '0',
    color: str = 'auto',
):
    """创建 OOXML border 元素。

    Args:
        tag: 边框标签名（如 'w:top', 'w:bottom', 'w:insideV'）
        val: 边框样式（'single' / 'none' / 'dashed' 等）
        sz: 边框粗细（单位 1/8 pt，'12' = 1.5pt）
        space: 边框与文字距离（pt）
        color: 颜色（'auto' 或十六进制 RGB）

    Returns:
        OxmlElement: 配置好的边框元素
    """
    border = OxmlElement(tag)
    border.set(qn('w:val'), val)
    border.set(qn('w:sz'), sz)
    border.set(qn('w:space'), space)
    border.set(qn('w:color'), color)
    return border


def make_shading_element(fill: str = 'F2F2F2', val: str = 'clear') -> OxmlElement:
    """创建单元格底纹元素。"""
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), val)
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    return shd


def set_fixed_table_layout(tbl_pr) -> None:
    """设置表格为固定列宽布局。"""
    tbl_layout = OxmlElement('w:tblLayout')
    tbl_layout.set(qn('w:type'), 'fixed')
    tbl_pr.append(tbl_layout)


def set_table_grid(tbl, col_widths_emu: list) -> None:
    """设置表格列宽（EMU 单位）。

    Args:
        tbl: 表格 _tbl 元素
        col_widths_emu: 每列宽度列表（EMU 单位）
    """
    new_grid = OxmlElement('w:tblGrid')
    for w in col_widths_emu:
        grid_col = OxmlElement('w:gridCol')
        # EMU → twips 近似换算
        grid_col.set(qn('w:w'), str(int(w / 914.4 * 1440)))
        new_grid.append(grid_col)
    # 移除旧 tblGrid
    for old_grid in tbl.findall(qn('w:tblGrid')):
        tbl.remove(old_grid)
    tbl.insert(1, new_grid)
