"""
去AI化领域调整模块
包含各行业领域的特定调整策略
"""
from typing import Dict

from log_helper import get_logger
log = get_logger(__name__)


class DomainAdjuster:
    """领域特定调整器"""

    def __init__(self):
        self.domain_handlers = {
            'facade': self._adjust_facade,
            'municipal': self._adjust_municipal,
            'decoration': self._adjust_decoration,
            'smart': self._adjust_smart,
            'green': self._adjust_green,
        }

    def adjust(self, text: str, domain: str) -> str:
        """根据领域调整文本"""
        handler = self.domain_handlers.get(domain)
        if handler:
            return handler(text)
        return text

    def _adjust_facade(self, text: str) -> str:
        """外立面排危工程调整"""
        # 添加外立面特定术语和表述
        adjustments = {
            '进行施工': '实施高空作业',
            '安全措施': '防坠落措施',
            '检查': '隐患排查',
        }
        for old, new in adjustments.items():
            text = text.replace(old, new)
        return text

    def _adjust_municipal(self, text: str) -> str:
        """市政工程调整"""
        adjustments = {
            '施工': '市政施工',
            '道路': '城市道路',
            '管道': '市政管网',
        }
        for old, new in adjustments.items():
            text = text.replace(old, new)
        return text

    def _adjust_decoration(self, text: str) -> str:
        """装修装饰工程调整"""
        adjustments = {
            '材料': '装修材料',
            '工艺': '装修工艺',
            '质量标准': '装修质量标准',
        }
        for old, new in adjustments.items():
            text = text.replace(old, new)
        return text

    def _adjust_smart(self, text: str) -> str:
        """智能化工程调整"""
        adjustments = {
            '系统': '智能系统',
            '设备': '智能化设备',
            '控制': '智能控制',
        }
        for old, new in adjustments.items():
            text = text.replace(old, new)
        return text

    def _adjust_green(self, text: str) -> str:
        """绿色施工调整"""
        adjustments = {
            '环保': '绿色环保',
            '节能': '节能减排',
            '材料': '绿色建材',
        }
        for old, new in adjustments.items():
            text = text.replace(old, new)
        return text
