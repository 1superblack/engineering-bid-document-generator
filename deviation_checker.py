"""
偏离表自动生成核心 v1.0 — P0 升级（对标 WPS AI / 喜鹊标书 AI 的"偏离表"卖点）

从 parser 解析结果中提取全部实质性 / 星号 / 废标 / 资格 / 红线条款，
与投标人（user_context / 知识库）能力逐条比对，自动生成偏离表数据。

偏离判定（行业通用约定）:
    - 无偏离: 完全满足招标文件要求
    - 正偏离: 优于招标文件要求（如注册资本 5000万 ≥ 要求 100万）
    - 负偏离: 不满足要求 → 高废标风险，必须人工处理
    - 未响应: 未提供任何响应内容
    - 部分偏离: 部分满足

设计原则:
    - 纯数据计算，不依赖 Word 渲染（渲染在 bid_technical.tables.deviation_table）
    - 与 user_context / 知识库解耦：能验证的尽量验证，不能验证的默认"无偏离"并标注承诺
    - 不阻断主流程：任何异常都降级为"跳过偏离表"，不影响标书生成
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from bid_core.logger import get_logger

log = get_logger(__name__)


# 偏离状态常量
DEVIATION_NONE = '无偏离'
DEVIATION_POSITIVE = '正偏离'
DEVIATION_NEGATIVE = '负偏离'
DEVIATION_PARTIAL = '部分偏离'
DEVIATION_NO_RESPONSE = '未响应'

# 类别常量
CAT_STAR = '星号条款'
CAT_DISQUALIFY = '废标条款'
CAT_QUALIFICATION = '资格要求'
CAT_REDLINE = '红线条款'
CAT_SUBSTANTIVE = '实质性条款'


class DeviationChecker:
    """偏离表校验器。

    用法:
        checker = DeviationChecker(parse_result, user_context)
        report = checker.generate()
        # report['items'] -> [{'req_id','category','content','clause_number',
        #                      'severity','is_mandatory','deviation','note','risk'}, ...]
    """

    def __init__(self, parse_result: Optional[Dict[str, Any]] = None,
                 user_context: Any = None):
        self.parse_result = parse_result or {}
        self.user_context = self._normalize_user_context(user_context)
        self._seq = 0

    # ────────────────────────────────────────────────────────────
    # 公共入口
    # ────────────────────────────────────────────────────────────
    def generate(self) -> Dict[str, Any]:
        """生成完整的偏离表报告。

        Returns:
            {
              'success': bool,
              'items': List[Dict],
              'summary': Dict[str, int],
              'risk_level': str,          # high / medium / low
              'risk_notes': List[str],
              'total_requirements': int,
            }
        """
        items: List[Dict[str, Any]] = []
        try:
            requirements = self.extract_requirements()
            for req in requirements:
                item = self._build_item(req)
                items.append(item)
        except Exception as exc:  # 偏离表不应阻断主流程
            log.warning('偏离表提取异常，降级跳过: %s', exc, exc_info=True)
            return self._empty_report()

        summary = {
            DEVIATION_NONE: 0, DEVIATION_POSITIVE: 0,
            DEVIATION_NEGATIVE: 0, DEVIATION_PARTIAL: 0,
            DEVIATION_NO_RESPONSE: 0,
        }
        risk_notes: List[str] = []
        for it in items:
            summary[it['deviation']] = summary.get(it['deviation'], 0) + 1
            if it.get('risk'):
                risk_notes.append(it['note'])

        risk_level = 'low'
        if summary[DEVIATION_NEGATIVE] > 0 or summary[DEVIATION_NO_RESPONSE] > 0:
            risk_level = 'high'
        elif summary[DEVIATION_PARTIAL] > 0:
            risk_level = 'medium'

        if risk_level == 'high':
            risk_notes.insert(0, '检测到负偏离/未响应条款，存在废标风险，请务必人工复核并补充响应材料。')

        return {
            'success': True,
            'items': items,
            'summary': summary,
            'risk_level': risk_level,
            'risk_notes': risk_notes,
            'total_requirements': len(items),
        }

    # ────────────────────────────────────────────────────────────
    # 要求提取
    # ────────────────────────────────────────────────────────────
    def extract_requirements(self) -> List[Dict[str, Any]]:
        """从 parse_result 归一化出全部需比对的条款。

        数据源优先级（去重靠 content 相似度）:
            star_clauses            → 星号/强制条款
            disqualify_clauses_structured → 废标条款
            qualification_reqs     → 资格要求
            red_line_clauses        → 红线条款
        """
        raw: List[Dict[str, Any]] = []
        pr = self.parse_result

        # 1. 废标条款（结构化）—— 招标文件明确列出的否决/废标条款，逐条承诺满足
        for dc in pr.get('disqualify_clauses_structured', []) or []:
            content = (dc.get('content') or '').strip()
            if not content:
                continue
            raw.append({
                'category': CAT_DISQUALIFY,
                'content': content,
                'clause_number': dc.get('clause_number', '') or '',
                'severity': dc.get('severity', 'critical'),
                'is_mandatory': True,
                'source': 'disqualify_clauses_structured',
            })

        # 2. 资格要求 —— 招标文件资格审查条件（真实强制性门槛）
        for qr in pr.get('qualification_reqs', []) or []:
            content = (qr.get('content') or '').strip()
            if not content:
                continue
            raw.append({
                'category': CAT_QUALIFICATION,
                'content': content,
                'clause_number': '',
                'severity': 'high' if qr.get('is_mandatory') else 'medium',
                'is_mandatory': bool(qr.get('is_mandatory', False)),
                'source': 'qualification_reqs',
            })

        # 说明：star_clauses / red_line_clauses 不再纳入偏离表。
        # 经验证，当前 parser 的 star_clauses 主要捕获《示范文本》投标人须知等
        # 铺垫文字（如"第二章投标人须知..."），并非真实星号/强制条款；red_line_clauses
        # 与 disqualify_clauses_structured 高度重叠。纳入会污染偏离表（163 行巨表），
        # 违背"仅按招标要求填写"。故仅保留招标文件明确列出的废标/资格条款。

        # 去重（基于内容前 30 字归一化）
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for r in raw:
            key = r['content'][:30]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
        return deduped

    # ────────────────────────────────────────────────────────────
    # 单条比对
    # ────────────────────────────────────────────────────────────
    def _build_item(self, req: Dict[str, Any]) -> Dict[str, Any]:
        self._seq += 1
        deviation, note, risk = self._verify(req)
        return {
            'req_id': f'D{self._seq:03d}',
            'category': req['category'],
            'content': req['content'],
            'clause_number': req.get('clause_number', ''),
            'severity': req.get('severity', 'medium'),
            'is_mandatory': req.get('is_mandatory', False),
            'deviation': deviation,
            'note': note,
            'risk': risk,
        }

    def _verify(self, req: Dict[str, Any]) -> Tuple[str, str, bool]:
        """返回 (偏离状态, 说明, 是否高风险)。

        验证策略:
            1. 尝试从条款中抽取数值阈值（注册资本/净资产/业绩个数/合同额/人员），
               并与 user_context 中可比对指标对照 → 正偏离/负偏离
            2. 星号/强制/废标条款默认"无偏离"，标注【必须响应】承诺
            3. 其余默认"无偏离"，标注承诺补充证明
        """
        content = req['content']
        severity = req.get('severity', 'medium')
        is_mandatory = req.get('is_mandatory', False)

        # —— 策略 1：数值阈值比对 ——
        num_result = self._try_numeric_verify(content)
        if num_result is not None:
            return num_result

        # —— 策略 2 / 3：文本承诺式响应 ——
        if is_mandatory or severity == 'critical':
            note = '【必须响应】投标人承诺完全满足本条款要求，详见对应章节内容。'
            risk = False
            return DEVIATION_NONE, note, risk

        note = '投标人承诺满足本条款要求（建议随标书附相关证明材料）。'
        return DEVIATION_NONE, note, False

    def _try_numeric_verify(self, content: str) -> Optional[Tuple[str, str, bool]]:
        """尝试抽取数值阈值并与投标人指标比对。"""
        # 单位 → (匹配正则, 投标人取值函数)
        patterns = [
            (r'(注册[资本资金]|开办资金|出资[额总额]|净资产)', self._company_capital),
            (r'(类似[项目业绩工程]|已完成[项目业绩])', self._project_count),
            (r'(合同[额金额]|中标金额|营业额)', self._contract_amount),
            (r'(项目[经理负责人员]|技术[负责总监人员]|注册[建造工程师]|高级[工程师职称])', self._personnel_count),
        ]
        for kw_pat, getter in patterns:
            if not re.search(kw_pat, content):
                continue
            req_val, unit = self._extract_number(content)
            if req_val is None:
                continue
            bidder_val = getter()
            if bidder_val is None:
                continue
            if bidder_val > req_val:
                note = (f'正偏离：投标人指标 {bidder_val}{unit} '
                        f'优于招标要求 {req_val}{unit}。')
                return DEVIATION_POSITIVE, note, False
            elif bidder_val == req_val:
                note = (f'无偏离：投标人指标 {bidder_val}{unit} '
                        f'满足招标要求 {req_val}{unit}。')
                return DEVIATION_NONE, note, False
            else:
                note = (f'负偏离：投标人指标 {bidder_val}{unit} '
                        f'低于招标要求 {req_val}{unit}，存在废标风险！')
                return DEVIATION_NEGATIVE, note, True
        return None

    # ────────────────────────────────────────────────────────────
    # user_context 指标获取
    # ────────────────────────────────────────────────────────────
    def _company_capital(self) -> Optional[float]:
        """投标人注册资本/净资产（单位: 万元）。"""
        company = self.user_context.get('company', {}) if isinstance(self.user_context, dict) else {}
        for key in ('registered_capital', 'net_assets', 'capital', '注册资本', '净资产'):
            val = company.get(key)
            if val is None:
                continue
            num = self._extract_number(str(val))[0]
            if num is not None:
                return num
        # 尝试从公司名/简介抽取
        desc = str(company.get('description', '') or company.get('intro', ''))
        if desc:
            return self._extract_number(desc)[0]
        return None

    def _project_count(self) -> Optional[float]:
        projects = self.user_context.get('similar_projects', []) if isinstance(self.user_context, dict) else []
        if isinstance(projects, list) and projects:
            return float(len(projects))
        return None

    def _contract_amount(self) -> Optional[float]:
        projects = self.user_context.get('similar_projects', []) if isinstance(self.user_context, dict) else []
        if not isinstance(projects, list) or not projects:
            return None
        amounts = []
        for p in projects:
            amt = p.get('amount') if isinstance(p, dict) else None
            if amt:
                v = self._extract_number(str(amt))[0]
                if v is not None:
                    amounts.append(v)
        return max(amounts) if amounts else None

    def _personnel_count(self) -> Optional[float]:
        persons = self.user_context.get('key_personnel', []) if isinstance(self.user_context, dict) else []
        if isinstance(persons, list) and persons:
            return float(len(persons))
        return None

    # ────────────────────────────────────────────────────────────
    # 工具方法
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_number(text: str) -> Tuple[Optional[float], str]:
        """从文本抽取第一个数值及其单位。

        Returns:
            (数值, 单位) — 无数值时 (None, '')
        """
        if not text:
            return None, ''
        # 优先匹配 亿元 / 万元 / 万 / 平方米 / ㎡ / 个 / 人 / 名 / 年
        # 数值捕获限定为「单可选小数点」小数，避免把条款号（如 1.4.4）误当数值导致 float 崩溃
        pats = [
            (r'(\d+(?:\.\d+)?)\s*亿元', '亿元'),
            (r'(\d+(?:\.\d+)?)\s*万元', '万元'),
            (r'(\d+(?:\.\d+)?)\s*万', '万'),
            (r'(\d+(?:\.\d+)?)\s*(平方米|㎡|m2|M2)', '㎡'),
            (r'(\d+(?:\.\d+)?)\s*(个|项)', '个'),
            (r'(\d+(?:\.\d+)?)\s*(人|名)', '人'),
            (r'(\d+(?:\.\d+)?)\s*年', '年'),
        ]
        for pat, unit in pats:
            m = re.search(pat, text)
            if m:
                try:
                    val = float(m.group(1))
                except ValueError:
                    continue  # 捕获到非数值（如条款号 1.4.4）→ 跳过本模式，尝试下一项
                if unit == '亿元':
                    val *= 10000  # 统一为万元
                return val, unit
        return None, ''

    @staticmethod
    def _normalize_user_context(uc: Any) -> Any:
        """统一 user_context 为 dict 形式（兼容 UserContext 实例与 dict）。"""
        if uc is None:
            return {}
        if isinstance(uc, dict):
            return uc
        # UserContext 实例
        if hasattr(uc, 'to_dict'):
            try:
                return uc.to_dict()
            except Exception:
                pass
        if hasattr(uc, 'data'):
            return getattr(uc, 'data') or {}
        return {}

    @staticmethod
    def _empty_report() -> Dict[str, Any]:
        return {
            'success': False,
            'items': [],
            'summary': {},
            'risk_level': 'low',
            'risk_notes': [],
            'total_requirements': 0,
        }


def check_deviation(parse_result: Optional[Dict[str, Any]],
                    user_context: Any = None) -> Dict[str, Any]:
    """模块级便捷入口。"""
    return DeviationChecker(parse_result, user_context).generate()
