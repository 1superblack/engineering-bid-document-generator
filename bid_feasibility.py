"""v8.9: 投标可行性预评估模块 — 解析招标文件后、生成标书前，快速判断"值不值得投"

对标喜鹊「投标决策评估」与钛投标「资质符合度自检」：
  - 输入 parse_result（已解析招标文件）+ 可选企业信息
  - 输出结构化可行性评估报告（资质匹配 / 风险等级 / 投标建议）
  - 不依赖 LLM，纯规则引擎 + 启发式打分，秒级出结果

用法:
    from bid_feasibility import assess_bid_feasibility
    report = assess_bid_feasibility(parse_result)
    print(report.to_text())       # 文本摘要
    print(report.to_dict())        # 结构化数据
    print(report.recommendation)   # "BID" / "CAUTION" / "PASS"
"""

import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any


@dataclass
class FeasibilityReport:
    """投标可行性评估报告"""

    # === 总评 ===
    recommendation: str  # "BID" / "CAUTION" / "PASS"
    overall_score: float  # 0-100, 综合可行性得分
    confidence: str  # "HIGH" / "MEDIUM" / "LOW" (数据完整度)

    # === 分项得分 ===
    qualification_match: float  # 资质匹配度 0-100
    risk_level: str  # "LOW" / "MEDIUM" / "HIGH" / "CRITICAL"
    risk_score: float  # 风险分(越低越好) 0-100
    complexity_score: float  # 标书编制复杂度 0-100(越高越难)
    time_pressure: str  # "RELAXED" / "MODERATE" / "TIGHT" / "CRITICAL"

    # === 细节 ===
    qualification_gaps: List[str]  # 可能不满足的资质要求
    risk_items: List[Dict[str, Any]]  # 废标风险清单
    score_item_count: int  # 评分项数量
    star_clause_count: int  # 星号条款数量
    red_line_count: int  # 红线/废标条款数量
    deadline_info: Optional[str] = None  # 截标时间信息
    quantity_summary: Optional[str] = None  # 工程量概要

    # === 建议 ===
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)

    def to_text(self) -> str:
        lines = [
            f"{'='*60}",
            f"  投标可行性预评估报告",
            f"{'='*60}",
            f"",
            f"  综合建议: {self._rec_label()} ({self.overall_score:.0f}/100)",
            f"  数据可信度: {self.confidence}",
            f"",
            f"--- 分项评估 ---",
            f"",
            f"  [1] 资质匹配度: {self.qualification_match:.0f}/100",
        ]
        if self.qualification_gaps:
            lines.append(f"      ⚠ 可能缺口:")
            for g in self.qualification_gaps[:8]:
                lines.append(f"        · {g}")
        else:
            lines.append(f"      ✅ 未发现明显资质障碍")

        lines += [
            f"",
            f"  [2] 废标风险等级: {self.risk_level} (风险分 {self.risk_score:.0f}/100)",
        ]
        if self.risk_items:
            lines.append(f"      检出到 {len(self.risk_items)} 项废标/否决风险:")
            for ri in self.risk_items[:6]:
                sev = ri.get('severity', '?')
                desc = ri.get('description', '')[:60]
                lines.append(f"        [{sev}] {desc}")

        lines += [
            f"",
            f"  [3] 标书复杂度: {'高' if self.complexity_score>70 else '中' if self.complexity_score>40 else '低'} ({self.complexity_score:.0f}/100)",
            f"      评分项 {self.score_item_count} 条 | 星号条款 {self.star_clause_count} 条 | 红线 {self.red_line_count} 条",
            f"",
            f"  [4] 时间压力: {self.time_pressure}",
        ]
        if self.deadline_info:
            lines.append(f"      截标: {self.deadline_info}")
        if self.quantity_summary:
            lines.append(f"      工程量: {self.quantity_summary}")

        lines += [f"", f"--- 建议 ---", f""]
        for s in self.suggestions:
            lines.append(f"  · {s}")

        lines += [f"", f"{'='*60}"]
        return "\n".join(lines)

    def _rec_label(self):
        map = {"BID": "✅ 建议投标", "CAUTION": "⚠️ 谨慎投标（有风险项需确认）", "PASS": "❌ 建议放弃（硬性条件不符）"}
        return map.get(self.recommendation, self.recommendation)


def assess_bid_feasibility(parse_result: Dict[str, Any],
                          enterprise_info: Optional[Dict[str, Any]] = None) -> FeasibilityReport:
    """
    主入口：基于解析后的招标文件结果，输出可行性评估。

    Args:
        parse_result: parser.parse_tender() 返回的字典（含 score_items/star_clauses 等）
        enterprise_info: 可选的企业信息字典，含:
            - qualifications: List[str] 企业已有资质列表
            - similar_projects: List[str] 类似业绩
            - max_contract_amount: 最大合同额(元)
            - team_size: 团队人数

    Returns:
        FeasibilityReport 结构化报告
    """
    info = enterprise_info or {}

    # --- [1] 资质匹配度 ---
    qual_match, qual_gaps = _score_qualification(parse_result, info)

    # --- [2] 风险评估 ---
    risk_level, risk_score, risk_items = _score_risk(parse_result)

    # --- [3] 复杂度 ---
    complexity = _score_complexity(parse_result)

    # --- [4] 时间压力 ---
    time_pressure, deadline_info, time_score = _score_time_pressure(parse_result)

    # --- [5] 综合评分与建议 ---
    overall, recommendation = _compute_overall(
        qual_match, risk_score, complexity, time_score
    )
    confidence = _assess_confidence(parse_result)

    # --- [6] 摘要字段 ---
    score_items = parse_result.get("score_items", [])
    star_clauses = parse_result.get("star_clauses", [])
    red_lines = parse_result.get("red_line_clauses", []) or []
    quantities = parse_result.get("quantities", [])
    deadlines = parse_result.get("deadlines", [])

    # --- [7] 生成建议 ---
    suggestions = _generate_suggestions(
        qual_match, risk_level, risk_score, complexity,
        time_pressure, len(score_items), len(risk_items), len(red_lines)
    )

    return FeasibilityReport(
        recommendation=recommendation,
        overall_score=overall,
        confidence=confidence,
        qualification_match=qual_match,
        risk_level=risk_level,
        risk_score=risk_score,
        complexity_score=complexity,
        time_pressure=time_pressure,
        qualification_gaps=qual_gaps,
        risk_items=risk_items,
        score_item_count=len(score_items),
        star_clause_count=len(star_clauses),
        red_line_count=len(red_lines),
        deadline_info=deadline_info,
        quantity_summary=_format_quantity_summary(quantities),
        suggestions=suggestions,
    )


# ==================== 内部评分函数 ====================

def _score_qualification(pr: Dict, info: Dict):
    """资质匹配度：检查招标文件的资质要求 vs 企业自有资质"""
    qual_reqs = pr.get("qualification_reqs", [])
    own_quals = info.get("qualifications", []) or []

    gaps = []
    matched = 0
    total = max(len(qual_reqs), 1)

    for req in qual_reqs:
        req_text = req.get("text", "") or req.get("raw", "") or str(req)
        req_text = req_text.strip()

        if not req_text or len(req_text) < 4:
            continue

        # 简单关键词匹配（企业资质列表中是否覆盖关键要求）
        matched_any = False
        if own_quals:
            for oq in own_quals:
                oq_str = oq.strip()
                if not oq_str:
                    continue
                # 如果企业资质包含招标要求中的任一关键词片段
                if _keyword_overlap(req_text, oq_str) > 0.2:
                    matched_any = True
                    break

        if matched_any:
            matched += 1
        else:
            # 记录为潜在缺口
            short = req_text[:50]
            gaps.append(short)

    score = (matched / total) * 100
    return min(score, 100.0), gaps


def _score_risk(pr: Dict):
    """废标风险评估：星号/红线/废标条款 → 风险等级"""
    stars = pr.get("star_clauses", [])
    red_lines = pr.get("red_line_clauses", []) or []

    risk_items = []

    # 星号条款 = critical
    for s in stars:
        text = s.get("text", "") or s.get("raw", "") or str(s)
        severity = s.get("severity", "critical")
        if text.strip():
            risk_items.append({
                "type": "star",
                "severity": severity,
                "description": text.strip()[:80],
            })

    # 红线/废标条款 = high/critical
    for rl in red_lines:
        text = rl.get("text", "") or rl.get("raw", "") or rl.get("clause", "") or str(rl)
        severity = rl.get("severity", "critical")
        if text.strip():
            risk_items.append({
                "type": "red_line",
                "severity": severity,
                "description": text.strip()[:80],
            })

    # 风险分：风险项越多分越高（越危险），上限 100
    raw = len(risk_items) * 10  # 每个风险项 +10 分
    risk_score = min(raw, 100.0)

    if risk_score >= 70:
        level = "CRITICAL"
    elif risk_score >= 40:
        level = "HIGH"
    elif risk_score >= 15:
        level = "MEDIUM"
    else:
        level = "LOW"

    return level, risk_score, risk_items


def _score_complexity(pr: Dict):
    """标书编制复杂度：评分项数 + 星号数 + 工程量参数"""
    scores = pr.get("score_items", [])
    stars = pr.get("star_clauses", [])
    quants = pr.get("quantities", [])
    red_lines = pr.get("red_line_clauses", []) or []

    score = 0
    # 评分项多 = 复杂（每条 +1 分，上限 40）
    score += min(len(scores) * 1.5, 40)
    # 星号条款 = 必须精准响应（每条 +5 分，上限 30）
    score += min(len(stars) * 5, 30)
    # 红线条款 = 高压（每条 +3 分，上限 20）
    score += min(len(red_lines) * 3, 20)
    # 工程量参数 = 需要精确填报（每类 +2 分，上限 10）
    score += min(len(quants) * 2, 10)

    return min(score, 100.0)


def _score_time_pressure(pr: Dict):
    """时间压力评估：从截标日期判断"""
    from datetime import datetime, timezone
    deadlines = pr.get("deadlines", [])
    now = datetime.now(timezone.utc)

    deadline_info = None
    pressure_score = 0  # 0=宽松, 100=极其紧急

    for d in deadlines:
        text = d.get("text", "") or d.get("raw", "") or str(d)
        date_val = d.get("date")
        if date_val:
            try:
                if hasattr(date_val, 'timestamp'):
                    dt = datetime.fromtimestamp(date_val.timestamp(), tz=timezone.utc)
                else:
                    dt = date_val
                delta = dt - now
                days = delta.total_seconds() / 86400
                if days < 0:
                    pressure_score = 100  # 已过期！
                elif days < 1:
                    pressure_score = 90
                elif days < 3:
                    pressure_score = 70
                elif days < 7:
                    pressure_score = 50
                elif days < 14:
                    pressure_score = 30
                else:
                    pressure_score = 10
                deadline_info = f"{dt.strftime('%Y-%m-%d %H:%M')} (剩余{max(0,int(days))}天)"
            except (TypeError, ValueError, OSError):
                pass

    if pressure_score >= 80:
        level = "CRITICAL"
    elif pressure_score >= 50:
        level = "TIGHT"
    elif pressure_score >= 20:
        level = "MODERATE"
    else:
        level = "RELAXED"

    return level, deadline_info, pressure_score


def _compute_overall(qual, risk, complex_, time_):
    """综合评分 → 投票建议"""
    # 加权模型：资质权重最高(40%)，风险次之(35%)，复杂度(15%)，时间(10%)
    overall = (
        qual * 0.40 +
        (100 - risk) * 0.35 +  # 风险分要反着算（风险越高越扣分）
        (100 - complex_) * 0.15 +
        (100 - time_) * 0.10
    )

    if qual < 50:
        rec = "PASS"  # 硬性条件不够
    elif risk >= 70 or qual < 65:
        rec = "CAUTION"  # 有明显风险
    else:
        rec = "BID"  # 可以投

    return round(overall, 1), rec


def _assess_confidence(pr: Dict) -> str:
    """评估数据完整度（有多少有效解析字段）"""
    fields = ["score_items", "star_clauses", "qualification_reqs",
              "quantities", "deadlines"]
    present = sum(1 for f in fields if pr.get(f))
    ratio = present / len(fields)

    if ratio >= 0.8:
        return "HIGH"
    elif ratio >= 0.4:
        return "MEDIUM"
    return "LOW"


def _keyword_overlap(a: str, b: str) -> float:
    """中文关键词重叠率（字符 bigram，正确处理子串包含）"""
    def _bigrams(s: str) -> set:
        # 仅保留中文字符，按 2 字滑动窗口生成 bigram 集合
        s = re.sub(r'[^\u4e00-\u9fff]', '', s or '')
        return set(s[i:i + 2] for i in range(len(s) - 1))

    sa, sb = _bigrams(a), _bigrams(b)
    if not sa or not sb:
        return 0.0
    inter = sa & sb
    return len(inter) / min(len(sa), len(sb))


def _format_quantity_summary(quants: List) -> str:
    if not quants:
        return None
    parts = []
    for q in quants[:5]:
        text = q.get("text", "") or q.get("raw", "") or ""
        val = q.get("value", "")
        if text and val:
            parts.append(f"{val}{text}")
    return ", ".join(parts) + ("..." if len(quants) > 5 else "")


def _generate_suggestions(qual, risk_level, risk_score, complexity,
                        time_press, n_scores, n_risks, n_red_lines):
    """生成针对性建议列表"""
    sug = []

    if qual < 60:
        sug.append("⛔ 资质匹配度偏低，核心资质可能不满足要求，建议先核对企业资质库后再决定是否投标。")
    elif qual < 80:
        sug.append("⚠ 部分资质要求可能存在缺口，请逐项核对后再启动标书编制。")

    if risk_level in ("CRITICAL", "HIGH"):
        sug.append(f"🚨 检测到 {n_risks} 项废标/否决风险（其中红线/废标条款 {n_red_lines} 项），建议优先梳理这些条款的响应策略，确保零遗漏。")
    elif risk_level == "MEDIUM":
        sug.append("⚡ 存在少量废标风险点，建议在编制时设置专项检查清单逐条响应。")

    if complexity > 70:
        sug.append(f"📋 标书复杂度高（{n_scores} 个评分项），建议提前规划章节分工并预留充足编制时间。")

    if time_press in ("TIGHT", "CRITICAL"):
        sug.append("⏰ 时间紧迫，建议优先保证废标条款响应和格式合规，技术方案的深度可适当调整。")

    if qual >= 75 and risk_score < 40 and complexity < 55 and time_press != "CRITICAL":
        sug.append("✅ 整体条件良好，可以启动标书编制流程。")

    if not sug:
        sug.append("建议上传招标文件获取更详细的解析结果以获得更准确的评估。")

    return sug
