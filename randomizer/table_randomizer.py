"""
表格数据随机化器 v6.0

对表格中的数值型数据进行合理偏移（±5-30%），使不同标书的表格不完全一致。
支持人员表、设备表、进度计划表等不同类型的差异化策略。
"""

import random
import re
import datetime
from typing import List, Optional

from log_helper import get_logger
log = get_logger(__name__)


class TableRandomizer:
    """表格数据随机化引擎"""

    # 各类表格的偏移比例配置
    OFFSET_RATIOS = {
        'personnel': 0.20,   # 人员配置表 ±20%
        'equipment': 0.30,   # 设备配置表 ±30%
        'schedule': 0.10,    # 进度计划表 日期偏移±3天
        'general': 0.15,     # 通用表格 ±15%
        'vary_min': 0.05,    # 微调模式下限
        'vary_max': 0.15,    # 微调模式上限
    }

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def randomize_table(
        self,
        table_data: List[List[str]],
        table_type: str = 'general'
    ) -> List[List[str]]:
        """
        表格数据随机化主入口

        Args:
            table_data: 二维表格数据（每行是字符串列表）
            table_type: 表格类型 (personnel/equipment/schedule/general)

        Returns:
            随机化后的表格数据
        """
        if not self.enabled or not table_data or len(table_data) < 2:
            return table_data

        result = [table_data[0]]  # 保留表头不变

        for row in table_data[1:]:
            new_row = [self._randomize_cell(cell, table_type) for cell in row]
            result.append(new_row)

        return result

    def _randomize_cell(self, cell: str, table_type: str) -> str:
        """对单个单元格进行随机化处理"""
        if not cell or not cell.strip():
            return cell

        cell = cell.strip()

        # 1. 纯整数 + 单位
        num_match = re.match(
            r'^(\d+)(人|台|辆|套|组|个|只|批|次|m²|m³|km|吨|㎡|项)?$',
            cell
        )
        if num_match:
            value = int(num_match.group(1))
            unit = num_match.group(2) or ''
            ratio = self.OFFSET_RATIOS.get(table_type, 0.15)
            new_value = self._apply_offset(value, ratio)
            return f'{new_value}{unit}'

        # 2. 浮点数 + 单位
        float_match = re.match(
            r'^(\d+\.?\d*)(人|台|辆|套|组|个|只|批|次|m²|m³|km|吨|㎡|项|kW|kVA|MPa|mm|cm)?$',
            cell
        )
        if float_match:
            value = float(float_match.group(1))
            unit = float_match.group(2) or ''
            ratio = self.OFFSET_RATIOS.get(table_type, 0.15)
            new_value = self._apply_offset(value, ratio, is_float=True)
            return f'{new_value}{unit}'

        # 3. 范围格式 "数字-数字"
        range_match = re.match(r'^(\d+)\s*[-~]\s*(\d+)(.*)$', cell)
        if range_match:
            low, high = int(range_match.group(1)), int(range_match.group(2))
            suffix = range_match.group(3)
            ratio = self.OFFSET_RATIOS.get(table_type, 0.15)
            new_low = self._apply_offset(low, ratio)
            new_high = self._apply_offset(high, ratio)
            if new_low > new_high:
                new_low, new_high = new_high, new_low
            return f'{new_low}~{new_high}{suffix}'

        # 4. 日期处理（schedule类型）
        if table_type == 'schedule':
            date_result = self._randomize_date(cell)
            if date_result != cell:
                return date_result

        # 5. 混合文本 "前缀数字单位"
        mixed_match = re.match(
            r'^(.*?)(\d+)(.*?)(人|台|辆|套|组|个|天|月|周|m²|m³|吨|kW|MPa|mm)?$',
            cell
        )
        if mixed_match and mixed_match.group(2):
            prefix = mixed_match.group(1)
            value = int(mixed_match.group(2))
            suffix = (mixed_match.group(3) or '') + (mixed_match.group(4) or '')
            ratio = self.OFFSET_RATIOS.get(table_type, 0.15)
            new_value = self._apply_offset(value, ratio)
            return f'{prefix}{new_value}{suffix}'

        return cell

    def _randomize_date(self, cell: str) -> str:
        """日期偏移处理"""
        # 格式1: "2025年6月15日"
        date_match = re.match(
            r'^(\d{4})[年/.-](\d{1,2})[月/.-](\d{1,2})[日号]?$',
            cell
        )
        if date_match:
            year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            day_offset = random.randint(-3, 3)
            try:
                dt = datetime.date(year, month, day) + datetime.timedelta(days=day_offset)
                return f'{dt.year}年{dt.month}月{dt.day}日'
            except ValueError:
                return cell

        # 格式2: "6月15日-7月20日"
        date_range_match = re.match(
            r'^(\d{1,2})[月/.-](\d{1,2})[日号]?\s*[-~至到]\s*(\d{1,2})[月/.-](\d{1,2})[日号]?$',
            cell
        )
        if date_range_match:
            m1, d1, m2, d2 = [int(date_range_match.group(i)) for i in range(1, 5)]
            try:
                ref_year = 2025
                dt1 = datetime.date(ref_year, m1, d1) + datetime.timedelta(days=random.randint(-3, 3))
                dt2 = datetime.date(ref_year, m2, d2) + datetime.timedelta(days=random.randint(-3, 3))
                if dt1 > dt2:
                    dt1, dt2 = dt2, dt1
                return f'{dt1.month}月{dt1.day}日~{dt2.month}月{dt2.day}日'
            except ValueError:
                return cell

        return cell

    @staticmethod
    def _apply_offset(value, ratio: float, is_float: bool = False):
        """对数值施加随机偏移"""
        offset = value * ratio * random.uniform(-1, 1)
        new_value = value + offset

        if is_float:
            return round(new_value, 2)
        else:
            return max(1, int(round(new_value)))

    # ════════════════════════════════════════════════════════
    # 专用表快速接口
    # ════════════════════════════════════════════════════════

    def randomize_personnel_table(self, table_data: List[List[str]]) -> List[List[str]]:
        """人员配置表专用随机化（±20%）"""
        return self.randomize_table(table_data, 'personnel')

    def randomize_equipment_table(self, table_data: List[List[str]]) -> List[List[str]]:
        """设备配置表专用随机化（±30%）"""
        return self.randomize_table(table_data, 'equipment')

    def randomize_schedule_table(self, table_data: List[List[str]]) -> List[List[str]]:
        """进度计划表专用随机化（日期偏移）"""
        return self.randomize_table(table_data, 'schedule')

    # ════════════════════════════════════════════════════════
    # v6.0 新增：表格微调模式（更精细的偏移控制）
    # ════════════════════════════════════════════════════════

    def vary_table_data(
        self,
        table: List[List[str]],
        min_ratio: float = 0.05,
        max_ratio: float = 0.15
    ) -> List[List[str]]:
        """
        表格数据微调（v6.0）

        比 randomize_table 更保守的偏移方式，适用于需要小幅调整的场景。

        Args:
            table: 表格数据
            min_ratio: 最小偏移比例
            max_ratio: 最大偏移比例

        Returns:
            微调后的表格数据
        """
        if not self.enabled or not table or len(table) < 2:
            return table

        result = [table[0]]

        for row in table[1:]:
            new_row = [
                self._vary_cell(cell, min_ratio, max_ratio) for cell in row
            ]
            result.append(new_row)

        return result

    def _vary_cell(self, cell: str, min_ratio: float, max_ratio: float) -> str:
        """单元格微调"""
        if not cell or not cell.strip():
            return cell

        cell = cell.strip()

        # 只处理纯数字或简单数字+单位
        num_match = re.match(r'^(\d+\.?\d*)(.*?)$', cell)
        if num_match:
            value = float(num_match.group(1))
            unit = num_match.group(2)

            # 在 min_ratio ~ max_ratio 范围内选择偏移比例
            ratio = random.uniform(min_ratio, max_ratio)
            offset = value * ratio * random.choice([-1, 1])
            new_value = value + offset

            is_float = '.' in num_match.group(1)
            if is_float:
                new_value = round(new_value, 2)
            else:
                new_value = max(1, int(round(new_value)))

            return f'{new_value}{unit}'

        return cell
