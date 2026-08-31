# -*- coding: utf-8 -*-
"""薄包装 Stage：把现有业务能力登记为管道单元。

每个 Stage 仅做「读取 ctx → 调用真实业务函数（延迟导入）→ 写回 ctx」这一层包装，
不改动任何业务逻辑。业务函数签名严格对照真实 Skill 源（v9.2.1 已移除 appendix_lockfill）的实际调用。

ADR-005 影响：企业画像相关能力已删除，故：
- 不登记「企业资质业绩响应表」Stage；
- 可行性评估的 enterprise_info 改为 req.user_context（不再取 enterprise_profile）；
- 评分闭环补强调用时 enterprise_profile 传 None。
"""
from __future__ import annotations

import os
from typing import Any

from .context import StageContext, StageStatus
from .stage import Stage
from .registry import register_stage


def _attr(req: Any, name: str, default: Any = None) -> Any:
    """安全读取请求字段（兼容 BidRequest 与 dict 入参）。"""
    if isinstance(req, dict):
        return req.get(name, default)
    return getattr(req, name, default)


@register_stage("tender_parse")
class TenderParseStage(Stage):
    """招标文件解析（对应 main.py 的 parse_tender 分支）。非阻断。"""

    name = "tender_parse"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        req = ctx.req
        if _attr(req, "tender_file") and not _attr(req, "parse_result"):
            return ctx.get("parse_result") is None
        return False

    def run(self, ctx: StageContext) -> None:
        from bid_core.parser import parse_tender

        req = ctx.req
        parsed = parse_tender(_attr(req, "tender_file"), bid_type=_attr(req, "bid_type"),
                              llm_client=ctx.llm_client,
                              enable_llm_parse=_attr(req, "enable_llm_parse", False))
        if parsed.get("score_items") or parsed.get("star_clauses") or \
           parsed.get("qualification_reqs") or parsed.get("red_line_clauses"):
            req.parse_result = parsed  # type: ignore[attr-defined]
            ctx.set("parse_result", parsed)
            ctx.data["parse_result"] = parsed
        else:
            # 与原逻辑一致：解析不出有效条款则忽略
            pass


@register_stage("feasibility")
class FeasibilityStage(Stage):
    """投标可行性预评估（assess_bid_feasibility）。非阻断。"""

    name = "feasibility"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        req = ctx.req
        return bool(_attr(req, "enable_feasibility")) and (
            ctx.get("parse_result") is not None or _attr(req, "parse_result") is not None
        )

    def run(self, ctx: StageContext) -> None:
        from bid_feasibility import assess_bid_feasibility

        parse_result = ctx.get("parse_result") or _attr(ctx.req, "parse_result")
        # ADR-005: 企业画像删除后，资质匹配信息回退为通用 user_context
        feas_info = _attr(ctx.req, "user_context") or {}
        feas = assess_bid_feasibility(parse_result, enterprise_info=feas_info)
        ctx.set("feasibility_report", feas.to_dict())


@register_stage("generation")
class GenerationStage(Stage):
    """核心生成（generate_bid / generate_bid_with_hooks）。阻断性——生成失败即整体失败。"""

    name = "generation"
    blocking = True

    def should_run(self, ctx: StageContext) -> bool:
        # 单章节模式由入口函数提前返回，不进入此 Stage
        return not (_attr(ctx.req, "chapter_only") and _attr(ctx.req, "chapter_title"))

    def run(self, ctx: StageContext) -> None:
        from bid_generator import generate_bid, generate_bid_with_hooks

        req = ctx.req
        # 转发大标书填充预算（CLI 设置；BidRequest.model_dump 会丢弃 extra 字段，
        # 故在此显式灌入 project_info，生成器按 per_chapter/global/para_per_page 读取）
        for _key in ("per_chapter_fill_cap", "global_fill_cap",
                     "fill_para_per_page", "llm_fill_call_budget"):
            _val = _attr(req, _key, None)
            if _val is not None:
                ctx.data[_key] = _val

        parse_result = ctx.get("parse_result") or _attr(req, "parse_result")

        target_pages = _attr(req, "target_pages", 120)
        detail_level = _attr(req, "detail_level")
        output_path = _attr(req, "output_path") or f"技术标书_{_attr(req, 'name')}.docx"
        user_context = _attr(req, "user_context")
        is_dark_bid = _attr(req, "is_dark_bid", False)
        dark_bid_filter_words = _attr(req, "dark_bid_filter_words")
        reference_file = _attr(req, "reference_file")
        enable_risk_grading = _attr(req, "enable_risk_grading", False)
        enable_mock_review = _attr(req, "enable_mock_review", False)
        enable_knowledge_base = _attr(req, "enable_knowledge_base", False)
        knowledge_base_path = _attr(req, "knowledge_base_path")
        enable_deai = _attr(req, "enable_deai", True)
        enable_format = _attr(req, "enable_format", True)
        enable_deviation_table = _attr(req, "enable_deviation_table", False)
        heading_font = _attr(req, "heading_font", "黑体")
        body_font = _attr(req, "body_font", "仿宋")
        randomize = _attr(req, "randomize", False)

        if _attr(req, "enable_hooks", False):
            res = generate_bid_with_hooks(
                project_info=ctx.data,
                target_pages=target_pages,
                output_path=output_path,
                parse_result=parse_result,
                user_context=user_context,
                detail_level=detail_level,
                randomize=randomize,
                is_dark_bid=is_dark_bid,
                dark_bid_filter_words=dark_bid_filter_words,
                add_cover=_attr(req, "add_cover", True),
                add_toc=_attr(req, "add_toc", True),
                add_page_numbers=_attr(req, "add_page_numbers", True),
                enable_deai=enable_deai,
                enable_format=enable_format,
                enable_deviation_table=enable_deviation_table,
                reference_file=reference_file,
                enable_risk_grading=enable_risk_grading,
                enable_mock_review=enable_mock_review,
                enable_knowledge_base=enable_knowledge_base,
                knowledge_base_path=knowledge_base_path,
                heading_font=heading_font,
                body_font=body_font,
                llm_client=ctx.llm_client,
            )
            result_path = res.get("doc_path", output_path)
            hooks_result = res.get("hooks", {})
        else:
            result_path = generate_bid(
                project_info=ctx.data,
                target_pages=target_pages,
                output_path=output_path,
                parse_result=parse_result,
                detail_level=detail_level,
                user_context=user_context,
                bid_type=_attr(req, "bid_type"),
                randomize=randomize,
                is_dark_bid=is_dark_bid,
                dark_bid_filter_words=dark_bid_filter_words,
                add_cover=_attr(req, "add_cover", True),
                add_toc=_attr(req, "add_toc", True),
                add_page_numbers=_attr(req, "add_page_numbers", True),
                enable_deviation_table=enable_deviation_table,
                reference_file=reference_file,
                enable_risk_grading=enable_risk_grading,
                enable_mock_review=enable_mock_review,
                enable_knowledge_base=enable_knowledge_base,
                knowledge_base_path=knowledge_base_path,
                heading_font=heading_font,
                body_font=body_font,
                llm_client=ctx.llm_client,
                # ADR-005: 不再传 enterprise_profile
            )
            hooks_result = None

        ctx.set("result_path", result_path)
        ctx.set("hooks_result", hooks_result)
        # D1-③：透传评审自检结论供 SummaryStage 与规则闸门交叉呈现
        # 仅在此处 pop 一次（hooks 分支与 else 分支共用 result_path，避免二次 pop 清空）
        try:
            from bid_generator import pop_evaluation_result
            ctx.set("evaluator_check", pop_evaluation_result(result_path))
        except Exception:  # noqa: BLE001
            pass


@register_stage("dedup")
class DedupStage(Stage):
    """跨文档防串标查重（check_duplicates）。非阻断。"""

    name = "dedup"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        result_path = ctx.get("result_path")
        return bool(_attr(ctx.req, "previous_bids")) and bool(result_path) and os.path.exists(result_path)

    def run(self, ctx: StageContext) -> None:
        from bid_generator import check_duplicates

        result_path = ctx.get("result_path")
        report = check_duplicates([result_path] + list(_attr(ctx.req, "previous_bids")), mode="标书")
        ctx.set("cross_doc_similarity", report.get("overall_max_similarity"))
        ctx.set("cross_doc_risk", report.get("risk_level"))


@register_stage("risk_library")
class RiskLibraryStage(Stage):
    """废标风险库核验（check_risk_library）。非阻断。"""

    name = "risk_library"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        result_path = ctx.get("result_path")
        return bool(_attr(ctx.req, "enable_risk_grading")) and bool(result_path) and os.path.exists(result_path)

    def run(self, ctx: StageContext) -> None:
        from checker.risk_library import check_risk_library, _extract_doc_text

        result_path = ctx.get("result_path")
        parse_result = ctx.get("parse_result") or _attr(ctx.req, "parse_result")
        doc_text = _extract_doc_text(result_path)
        ctx.set("risk_library_findings", check_risk_library(parse_result, doc_text))


@register_stage("scoring_reinforce")
class ScoringReinforceStage(Stage):
    """评分响应闭环补强（run_scoring_reinforcement）。非阻断。"""

    name = "scoring_reinforce"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        result_path = ctx.get("result_path")
        return (
            bool(_attr(ctx.req, "enable_scoring_reinforce"))
            and (ctx.get("parse_result") or _attr(ctx.req, "parse_result")) is not None
            and bool(result_path)
            and os.path.exists(result_path)
        )

    def run(self, ctx: StageContext) -> None:
        from scoring_reinforce import run_scoring_reinforcement

        parse_result = ctx.get("parse_result") or _attr(ctx.req, "parse_result")
        result_path = ctx.get("result_path")
        # ADR-005: enterprise_profile 已删除，不再传该参数
        ctx.set("scoring_reinforcement", run_scoring_reinforcement(parse_result, result_path))


# ---------------------------------------------------------------------------
# ADR-005 已删除的能力（不再登记为 Stage）：
#   - 企业资质业绩库加载（enterprise_profile.load_profile）
#   - 资质业绩响应表生成与注入（enterprise_profile.build_response_table / inject_section）
#   - 技术标附表锁格式配置（appendix_lockfill）：真实 Skill 源未包含该模块
# 原 main.py 通过 enterprise_profile 联动 feasibility / 生成 / 响应表 / 评分补强
# 四处，现已分别回退为「通用模板 / 规则引擎」实现，无需独立 Stage。
# ---------------------------------------------------------------------------
