"""
全局配置常量 v1.0 — P2-1 重构

集中管理散落在各模块中的魔法数字，提供带注释的命名常量。
所有数值的来源、含义和调整依据都在此文件中记录。
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════
# 页数与深度
# ══════════════════════════════════════════════════════════════════

DEFAULT_TARGET_PAGES = 300
"""默认目标页数 — 当 target_pages=0 时使用"""

TABLE_RESERVED_PAGES = 20
"""附表预留页数 — 从 target_pages 中扣除，用于内容页数计算"""

# detail_level 自动计算阈值
DETAIL_LEVEL_FULL_THRESHOLD = 200      # ≥200页 → level 3 (完整)
DETAIL_LEVEL_STANDARD_THRESHOLD = 50   # ≤50页 → level 1 (精简)
# 50 < pages < 200 → level 2 (标准)

# 评分策略 detail_level (1-5) 页数上限
SCORE_DETAIL_PAGE_LIMITS = {
    5: 35,   # 权重≥15%
    4: 30,   # 权重10-15%
    3: 25,   # 权重5-10%
    2: 15,   # 权重<5%
    1: 10,   # 无评分项
}

# 评分项权重占比阈值
SCORE_RATIO_HIGH = 0.15    # ≥15% → detail_level 5
SCORE_RATIO_MEDIUM = 0.10  # ≥10% → detail_level 4
SCORE_RATIO_LOW = 0.05     # ≥5% → detail_level 3

# 页数估算系数
PARAGRAPHS_PER_PAGE = 25   # 约25个段落≈1页
TABLES_PAGE_MULTIPLIER = 2  # 每个表格≈2页

# ══════════════════════════════════════════════════════════════════
# 字体与排版
# ══════════════════════════════════════════════════════════════════

DEFAULT_HEADING_FONT = '黑体'
DEFAULT_BODY_FONT = '仿宋'

# 字号（单位: Pt）
FONT_SIZE_H1 = 22
FONT_SIZE_H2 = 16
FONT_SIZE_H3 = 14
FONT_SIZE_H4 = 12
FONT_SIZE_BODY = 12        # 仿宋小三 ≈ 12pt
FONT_SIZE_TABLE = 10
FONT_SIZE_TABLE_HEADER = 10
FONT_SIZE_COVER_TITLE = 28
FONT_SIZE_COVER_SUBTITLE = 18

# 页面尺寸（单位: Cm）
PAGE_WIDTH_A4 = 21.0
PAGE_HEIGHT_A4 = 29.7
MARGIN_LEFT = 2.5
MARGIN_RIGHT = 2.5
MARGIN_TOP = 3.0
MARGIN_BOTTOM = 2.5

# 表格
WIDE_TABLE_THRESHOLD = 8  # 列数>8 视为宽表
TABLE_COLUMN_WIDTH_CM = 2.0  # 默认列宽

# 行距
LINE_SPACING = 1.5        # 正文行距
HEADING_SPACING_BEFORE = 12  # 标题段前距
HEADING_SPACING_AFTER = 6    # 标题段后距

# ══════════════════════════════════════════════════════════════════
# 修复与检查
# ══════════════════════════════════════════════════════════════════

MAX_REPAIR_ROUNDS = 3         # 合规修复最大轮数
MIN_CHAPTER_CHARS = 200       # 章节最小字数阈值
MIN_TECHNICAL_BID_PAGES = 100 # 技术标最少页数（合理性校验）

# 评分项覆盖率阈值
COVERAGE_WARNING_THRESHOLD = 0.80   # <80% 告警
SCORE_PREDICTION_WARNING = 60.0     # <60% 告警

# ══════════════════════════════════════════════════════════════════
# 横道图
# ══════════════════════════════════════════════════════════════════

GANTT_DEFAULT_DURATION = 90   # 默认工期（天）
GANTT_DAYS_PER_MONTH = 30     # 每月天数（横道图计算用）
GANTT_FONT_SIZE = 8           # 横道图表格字号

# ══════════════════════════════════════════════════════════════════
# 日志
# ══════════════════════════════════════════════════════════════════

LOG_DEFAULT_LEVEL = 'INFO'
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_FILE_BACKUP_COUNT = 7              # 保留7天日志
