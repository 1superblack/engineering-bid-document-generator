"""字体白名单与默认值 — formatter 共享常量。

拆分自原 formatter.py v7.0。
所有字体安全降级逻辑集中在此处，便于维护和扩展。
"""

# 标题字体白名单
HEADING_FONTS: dict[str, str] = {
    '黑体': '黑体',
    '宋体': '宋体',
    '微软雅黑': '微软雅黑',
    '楷体': '楷体',
    '华文仿宋': '华文仿宋',
    '仿宋': '仿宋',
}

# 正文字体白名单
BODY_FONTS: dict[str, str] = {
    '仿宋': '仿宋',
    '仿宋_GB2312': '仿宋_GB2312',
    '宋体': '宋体',
    '微软雅黑': '微软雅黑',
    '楷体': '楷体',
    '黑体': '黑体',
}

DEFAULT_HEADING_FONT = '黑体'
DEFAULT_BODY_FONT = '仿宋'


def safe_heading_font(name: str | None) -> str:
    """安全获取标题字体，不在白名单则降级到默认。"""
    if name and name in HEADING_FONTS:
        return name
    return DEFAULT_HEADING_FONT


def safe_body_font(name: str | None) -> str:
    """安全获取正文字体，不在白名单则降级到默认。"""
    if name and name in BODY_FONTS:
        return name
    return DEFAULT_BODY_FONT
