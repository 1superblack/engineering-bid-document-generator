"""
富内容引擎 - 句子生成模块
包含各类专业领域的句子生成器
"""
import random
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class SentenceGenerator:
    """句子生成器基类"""

    def __init__(self, templates: dict = None):
        """
        Args:
            templates: 模板字典（按类别组织）
        """
        self.templates = templates or {}
        self.stats = {
            'sentences_generated': 0,
            'by_type': {},
        }

    def generate(self, category: str, ctx: Dict[str, Any],
                 rng: int = None) -> str:
        """生成指定类别的句子

        Args:
            category: 句子类别
            ctx: 上下文信息
            rng: 随机种子

        Returns:
            生成的句子文本
        """
        if rng is not None:
            random.seed(rng)

        pool = self.templates.get(category, [])
        if not pool:
            log.warning(f"无模板可用: {category}")
            return ""

        template = random.choice(pool)
        sentence = self._fill_template(template, ctx)

        self.stats['sentences_generated'] += 1
        self.stats['by_type'][category] = self.stats['by_type'].get(category, 0) + 1

        return sentence

    def _fill_template(self, template: str, ctx: Dict[str, Any]) -> str:
        """填充模板占位符"""
        try:
            return template.format(**ctx)
        except KeyError as e:
            log.debug(f"模板填充缺少变量: {e}")
            return template


class DomainSentenceGenerator(SentenceGenerator):
    """特定领域句子生成器"""

    DOMAIN_TEMPLATES = {
        'quality': [
            "本项目严格执行ISO9001质量管理体系标准",
            "建立完善的三级质量检验制度",
            "实施关键工序旁站监督制度",
            "原材料进场100%复验合格后方可使用",
        ],
        'safety': [
            "全面落实安全生产责任制",
            "坚持安全第一、预防为主的方针",
            "建立安全隐患排查治理长效机制",
            "特殊作业人员100%持证上岗",
        ],
        'schedule': [
            "采用网络计划技术进行进度控制",
            "建立周/月/季三级进度计划体系",
            "实施动态进度跟踪与纠偏措施",
        ],
    }

    def __init__(self):
        super().__init__(self.DOMAIN_TEMPLATES)

    def generate_quality_sentence(self, ctx: Dict, rng: int = None) -> str:
        """生成质量控制相关句子"""
        return self.generate('quality', ctx, rng)

    def generate_safety_sentence(self, ctx: Dict, rng: int = None) -> str:
        """生成安全文明施工相关句子"""
        return self.generate('safety', ctx, rng)


class TechnicalSentenceGenerator(SentenceGenerator):
    """技术方案句子生成器"""

    TECH_TEMPLATES = {
        'bim': [
            "采用BIM技术进行管线综合排布，提前发现并解决碰撞问题",
            "利用BIM模型进行4D进度模拟，优化施工顺序和资源配置",
        ],
        'green': [
            "严格执行绿色施工标准，减少施工过程对环境的影响",
            "采用装配式建造技术减少现场湿作业和建筑垃圾产生",
        ],
        'smart': [
            "引入智慧工地管理系统实现施工全过程数字化管控",
            "应用物联网技术对大型设备运行状态进行实时监测",
        ],
    }

    def __init__(self):
        super().__init__(self.TECH_TEMPLATES)

    def generate_bim_sentence(self, ctx: Dict, rng: int = None) -> str:
        """生成BIM技术应用相关句子"""
        return self.generate('bim', ctx, rng)

    def generate_green_sentence(self, ctx: Dict, rng: int = None) -> str:
        """生成绿色施工相关句子"""
        return self.generate('green', ctx, rng)

    def generate_smart_sentence(self, ctx: Dict, rng: int = None) -> str:
        """生成智能化应用相关句子"""
        return self.generate('smart', ctx, rng)


class MeasureSentenceGenerator(SentenceGenerator):
    """保证措施句子生成器"""

    MEASURE_TEMPLATES = {
        'organization': [
            "成立以项目经理为组长的专项领导小组",
            "建立健全项目管理体系明确各级职责分工",
        ],
        'technical': [
            "编制专项施工方案并组织专家论证",
            "进行详细的技术交底和安全教育",
        ],
        'emergency': [
            "制定应急预案并定期组织演练",
            "配置充足的应急物资和救援设备",
        ],
    }

    def __init__(self):
        super().__init__(self.MEASURE_TEMPLATES)

    def generate_organization_sentence(self, ctx: Dict, rng: int = None) -> str:
        """生成组织保障措施句子"""
        return self.generate('organization', ctx, rng)

    def generate_emergency_sentence(self, ctx: Dict, rng: int = None) -> str:
        """生成应急预案相关句子"""
        return self.generate('emergency', ctx, rng)
