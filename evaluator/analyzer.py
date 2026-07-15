"""
评审分析引擎
执行评分计算和结果分析
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .scoring import (
    ScoringCriteria,
    ScoreItem,
    get_criteria_for_bid_type,
    calculate_total_weight,
)

log = logging.getLogger(__name__)


class EvaluatorEngine:
    """评审分析引擎 v2.0

    功能：
    - 根据评分标准进行逐项评分
    - 计算加权总分
    - 生成评审意见
    - 识别弱项并给出建议
    """

    def __init__(self, bid_type: str = 'technical'):
        """
        Args:
            bid_type: 标书类型
        """
        self.bid_type = bid_type
        self.criteria = get_criteria_for_bid_type(bid_type)
        self.scores: Dict[str, ScoreItem] = {}
        self.evaluation_time: Optional[datetime] = None

        # 统计信息
        self.stats = {
            'items_evaluated': 0,
            'total_score': 0,
            'max_possible': 0,
            'average_score': 0,
        }

        log.info(f"EvaluatorEngine初始化 | 类型={bid_type} | "
                f"评分项数={len(self.criteria)}")

    # 14 个竞品对标型维度（v7.16~v7.31 逐轮对比 WPS AI/喜鹊标书/钛投标/红点智标补强）
    _COMPETE_DIMS = [
        {'name': 'BIM深度应用', 'keywords': ['BIM', '碰撞检查', '管线综合'],
         'gap': '竞品多停留在 BIM 建模可视化，未实现碰撞检查与管线综合优化闭环'},
        {'name': '绿色施工/双碳', 'keywords': ['碳排放', '双碳', '绿色施工', '节能'],
         'gap': '竞品缺乏量化碳减排指标，双碳达标论述薄弱'},
        {'name': '质量通病防治', 'keywords': ['质量通病'],
         'gap': '竞品通病清单泛泛而谈，缺典型通病专项防治'},
        {'name': '危大工程管控', 'keywords': ['专家论证', '危大', '专项方案'],
         'gap': '竞品危大工程仅罗列规范，缺专家论证闭环'},
        {'name': '创优奖项策划', 'keywords': ['鲁班', '国优', '创优', '奖项'],
         'gap': '竞品创优目标缺失或口号化'},
        {'name': '智慧工地监管', 'keywords': ['实名制', '智慧工地', '人脸识别', '闸机'],
         'gap': '竞品智慧工地监管手段落后'},
        {'name': '成品保护/保修', 'keywords': ['成品保护'],
         'gap': '竞品成品保护交接制度缺失'},
        {'name': '测量与试验检测', 'keywords': ['见证取样', 'CMA', '试验检测'],
         'gap': '竞品试验检测第三方溯源不足'},
        {'name': '季节/特殊工况', 'keywords': ['冬期', '季节', '雨季', '特殊工况'],
         'gap': '竞品未针对季节工况专项部署'},
        {'name': '量化硬指标', 'keywords': ['合格率', '量化', '指标', '≥', '降低'],
         'gap': '竞品量化硬指标缺失，以定性描述为主'},
        {'name': '评分项逐条响应', 'keywords': ['针对', '评分项', '逐条', '专项落实'],
         'gap': '竞品评分项响应未逐条闭环'},
        {'name': '应急预案与演练', 'keywords': ['应急', '演练', '预案'],
         'gap': '竞品应急预案缺演练闭环'},
        {'name': '安全文明/CI形象', 'keywords': ['围挡', '七牌一图', '文明施工', 'CI'],
         'gap': '竞品安全文明 CI 形象标准化不足'},
        {'name': '劳务/工资保障', 'keywords': ['工资专用账户', '劳务', '分账', '总包代发', '农民工'],
         'gap': '竞品劳务工资保障链条不完整'},
    ]

    @classmethod
    def _scan_compete_coverage(cls, paras: List[str]) -> Dict[str, Any]:
        """扫描正文段落，统计 14 个竞争力维度的落地覆盖情况。

        Args:
            paras: 正文段落文本列表
        Returns:
            {'present': [{'name': ...}], 'missing': [{'name':..., 'gap':...}],
             'coverage_rate': float(0-100)}
        """
        present: List[Dict[str, str]] = []
        missing: List[Dict[str, str]] = []
        for dim in cls._COMPETE_DIMS:
            hit = any(any(kw in p for kw in dim['keywords']) for p in paras)
            if hit:
                present.append({'name': dim['name']})
            else:
                missing.append({'name': dim['name'], 'gap': dim['gap']})
        total = len(cls._COMPETE_DIMS)
        coverage_rate = (len(present) / total * 100.0) if total else 0.0
        return {
            'present': present,
            'missing': missing,
            'coverage_rate': coverage_rate,
        }

    @classmethod
    def _render_compete_markdown(cls, res: Dict[str, Any]) -> str:
        """将 _scan_compete_coverage 结果渲染为 Markdown 章节。"""
        lines = ['## 技术标竞争力维度覆盖自检', '']
        lines.append(f"维度覆盖率：**{res['coverage_rate']:.1f}%**")
        lines.append('')
        lines.append('### 已落地维度')
        lines.append('')
        for d in res['present']:
            lines.append(f"- {d['name']}")
        lines.append('')
        if res['missing']:
            lines.append('### 未落地维度（竞品对标差距）')
            lines.append('')
            for d in res['missing']:
                lines.append(f"- {d['name']}：{d['gap']}")
            lines.append('')
        return '\n'.join(lines)

    def score_item(self, criteria_id: str, score: float,
                   max_score: float = None, comments: str = '',
                   evidence: List[str] = None) -> ScoreItem:
        """对单个评分项打分

        Args:
            criteria_id: 评分标准ID
            score: 得分
            max_score: 最大分值（可选，默认使用标准定义）
            comments: 评语
            evidence: 证据列表

        Returns:
            ScoreItem对象

        Raises:
            ValueError: 如果criteria_id不存在或分数超出范围
        """
        if criteria_id not in self.criteria:
            raise ValueError(f"未知的评分标准ID: {criteria_id}")

        criteria = self.criteria[criteria_id]
        actual_max = max_score or criteria.max_score

        if score < 0 or score > actual_max:
            raise ValueError(f"分数{score}超出范围[0, {actual_max}]")

        item = ScoreItem(
            item_id=criteria_id,
            name=criteria.name,
            score=score,
            max_score=actual_max,
            comments=comments,
            evidence=evidence or [],
        )

        self.scores[criteria_id] = item
        self.stats['items_evaluated'] += 1

        log.debug(f"评分完成: {criteria.name} = {score}/{actual_max}")

        return item

    def calculate_weighted_total(self) -> float:
        """计算加权总分

        Returns:
            加权总分（满分通常为100）
        """
        total = 0.0
        total_weighted_max = 0.0

        for criteria_id, item in self.scores.items():
            if criteria_id in self.criteria:
                criteria = self.criteria[criteria_id]
                weighted_score = (item.score / item.max_score * criteria.weighted_max)
                total += weighted_score
                total_weighted_max += criteria.weighted_max

        # 归一化到100分制
        if total_weighted_max > 0:
            total = total / total_weighted_max * 100

        return round(total, 2)

    def get_analysis(self) -> Dict[str, Any]:
        """获取完整分析结果

        Returns:
            分析结果字典，包含各项得分、总分、排名等
        """
        now = datetime.now()
        self.evaluation_time = now

        # 计算总分
        total_score = self.calculate_weighted_total()

        # 统计各等级数量
        grade_distribution = {
            'excellent': 0,  # >=90%
            'good': 0,       # >=75%
            'fair': 0,       # >=60%
            'poor': 0,       # <60%
        }

        for item in self.scores.values():
            pct = item.percentage
            if pct >= 90:
                grade_distribution['excellent'] += 1
            elif pct >= 75:
                grade_distribution['good'] += 1
            elif pct >= 60:
                grade_distribution['fair'] += 1
            else:
                grade_distribution['poor'] += 1

        # 识别弱项（得分率<70%的）
        weak_items = [
            {'id': item.item_id, 'name': item.name,
             'percentage': item.percentage, 'comments': item.comments}
            for item in self.scores.values()
            if item.percentage < 70
        ]

        # 更新统计
        self.stats['total_score'] = total_score
        self.stats['max_possible'] = len(self.criteria) * 100
        self.stats['average_score'] = (
            sum(item.score for item in self.scores.values()) /
            max(len(self.scores), 1)
        )

        result = {
            'bid_type': self.bid_type,
            'evaluation_time': now.isoformat(),
            'summary': {
                'total_score': total_score,
                'max_score': 100.0,
                'grade': self._get_grade(total_score),
                'rank_estimate': self._estimate_rank(total_score),
            },
            'scores': {
                cid: {
                    'name': item.name,
                    'score': item.score,
                    'max_score': item.max_score,
                    'percentage': round(item.percentage, 1),
                    'comments': item.comments,
                }
                for cid, item in self.scores.items()
            },
            'statistics': {
                **self.stats,
                'grade_distribution': grade_distribution,
            },
            'weak_items': weak_items,
            'recommendations': self._generate_recommendations(weak_items),
        }

        log.info(f"分析完成 | 总分={total_score} | 等级={result['summary']['grade']}")

        return result

    def _get_grade(self, score: float) -> str:
        """根据分数确定等级"""
        if score >= 90:
            return '优秀'
        elif score >= 80:
            return '良好'
        elif score >= 70:
            return '中等'
        elif score >= 60:
            return '及格'
        else:
            return '不及格'

    def _estimate_rank(self, score: float) -> str:
        """估算相对排名"""
        if score >= 95:
            return '前10%'
        elif score >= 85:
            return '前30%'
        elif score >= 75:
            return '前50%'
        elif score >= 65:
            return '后50%'
        else:
            return '后20%'

    def _generate_recommendations(self,
                                 weak_items: List[Dict]) -> List[str]:
        """根据弱项生成改进建议"""
        recommendations = []

        for item in weak_items[:5]:  # 只针对主要弱项
            name = item.get('name', '')
            pct = item.get('percentage', 0)
            recommendations.append(
                f"[{name}] 当前得分{pct:.0f}%，"
                f"建议补充相关内容提升至70%以上"
            )

        if not weak_items:
            recommendations.append("整体表现均衡，继续保持")

        return recommendations


class ComparativeEvaluator:
    """对比评估器（用于多份标书对比）"""

    def __init__(self):
        self.evaluations: List[Dict] = []

    def add_evaluation(self, evaluation_result: Dict) -> None:
        """添加一份标书的评估结果"""
        self.evaluations.append(evaluation_result)

    def compare(self) -> Dict[str, Any]:
        """生成对比报告

        Returns:
            对比结果字典
        """
        if len(self.evaluations) < 2:
            raise ValueError("至少需要2份标书才能对比")

        # 按总分排序
        sorted_evals = sorted(
            self.evaluations,
            key=lambda e: e.get('summary', {}).get('total_score', 0),
            reverse=True,
        )

        comparison = {
            'total_compared': len(self.evaluations),
            'ranking': [],
            'best_practices': [],
            'common_weaknesses': [],
        }

        for i, eval_result in enumerate(sorted_evals):
            comparison['ranking'].append({
                'rank': i + 1,
                'total_score': eval_result.get('summary', {}).get('total_score'),
                'grade': eval_result.get('summary', {}).get('grade'),
            })

        # 提取最佳实践和共性问题
        # （简化实现）

        return comparison
