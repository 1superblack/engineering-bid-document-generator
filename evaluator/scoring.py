"""
评分标准模块
定义各类评审标准和评分规则
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class ScoringCriteria:
    """评分标准"""
    criteria_id: str
    name: str
    description: str
    max_score: float = 100.0
    weight: float = 1.0
    sub_items: List[Dict] = field(default_factory=list)

    @property
    def weighted_max(self) -> float:
        return self.max_score * self.weight


@dataclass
class ScoreItem:
    """单项得分"""
    item_id: str
    name: str
    score: float
    max_score: float
    comments: str = ''
    evidence: List[str] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0


# ════════════════════════════════════════════════════════════════
# 预定义评分标准集（常见标书类型）
# ════════════════════════════════════════════════════════════════

TECHNICAL_BID_CRITERIA = {
    'tech_solution': ScoringCriteria(
        criteria_id='T001',
        name='技术方案',
        description='施工组织设计、技术方案的完整性和可行性',
        max_score=30,
        weight=1.0,
        sub_items=[
            {'id': 'T001_1', 'name': '施工方案完整性', 'weight': 0.3},
            {'id': 'T001_2', 'name': '技术路线合理性', 'weight': 0.4},
            {'id': 'T001_3', 'name': '创新点', 'weight': 0.3},
        ],
    ),
    'quality_control': ScoringCriteria(
        criteria_id='T002',
        name='质量控制',
        description='质量保证体系、控制措施的完善程度',
        max_score=20,
        weight=1.0,
        sub_items=[
            {'id': 'T002_1', 'name': '质量管理体系', 'weight': 0.4},
            {'id': 'T002_2', 'name': '关键工序控制', 'weight': 0.3},
            {'id': 'T002_3', 'name': '检测手段', 'weight': 0.3},
        ],
    ),
    'safety_management': ScoringCriteria(
        criteria_id='T003',
        name='安全文明施工',
        description='安全保障措施和文明施工管理',
        max_score=15,
        weight=1.0,
    ),
    'schedule_control': ScoringCriteria(
        criteria_id='T004',
        name='进度计划',
        description='进度安排的合理性和保障措施',
        max_score=15,
        weight=1.0,
    ),
    'resource_allocation': ScoringCriteria(
        criteria_id='T005',
        name='资源配置',
        description='人员、设备、材料等资源配置情况',
        max_score=10,
        weight=1.0,
    ),
    'experience_qualification': ScoringCriteria(
        criteria_id='T006',
        name='业绩与资质',
        description='类似项目经验和企业资质',
        max_score=10,
        weight=1.0,
    ),
}

COMMERCIAL_BID_CRITERIA = {
    'price': ScoringCriteria(
        criteria_id='C001',
        name='投标报价',
        description='报价的合理性和竞争力',
        max_score=50,
        weight=2.0,
    ),
    'commercial_terms': ScoringCriteria(
        criteria_id='C002',
        name='商务条款响应',
        description='对合同条款的响应程度',
        max_score=25,
        weight=1.0,
    ),
    'payment_schedule': ScoringCriteria(
        criteria_id='C003',
        name='付款条件',
        description='付款方式和周期的合理性',
        max_score=15,
        weight=1.0,
    ),
    'warranty_service': ScoringCriteria(
        criteria_id='C004',
        name='售后服务',
        description='质保期和服务承诺',
        max_score=10,
        weight=1.0,
    ),
}


def get_criteria_for_bid_type(bid_type: str) -> Dict[str, ScoringCriteria]:
    """根据标书类型获取评分标准

    Args:
        bid_type: 标书类型 ('technical' | 'commercial' | 'qualification')

    Returns:
        评分标准字典
    """
    type_map = {
        'technical': TECHNICAL_BID_CRITERIA,
        'commercial': COMMERCIAL_BID_CRITERIA,
        'qualification': {},  # 资格标通常采用合格/不合格制
    }

    return type_map.get(bid_type, {})


def calculate_total_weight(criteria_dict: Dict[str, ScoringCriteria]) -> float:
    """计算总权重"""
    return sum(c.weight for c in criteria_dict.values())


def validate_criteria(criteria: ScoringCriteria) -> List[str]:
    """验证评分标准的有效性

    Returns:
        问题列表（空表示无问题）
    """
    issues = []

    if criteria.max_score <= 0:
        issues.append(f"最大分值必须大于0: {criteria.name}")

    if criteria.weight <= 0:
        issues.append(f"权重必须大于0: {criteria.name}")

    total_sub_weight = sum(s.get('weight', 0) for s in criteria.sub_items)
    if criteria.sub_items and abs(total_sub_weight - 1.0) > 0.01:
        issues.append(f"子项权重之和不为1: {criteria.name} ({total_sub_weight:.2f})")

    return issues
