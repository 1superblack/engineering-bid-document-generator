# -*- coding: utf-8 -*-
"""技术标优化专项 Stage 模块（T1–T10 路线中的新增能力）。

本模块集中承载「技术标优化清单」里的新增 Stage，与 report_stages.py（既有交付物 Stage）
解耦，降低对 502 回归基线的冲击。所有 Stage 均为 opt-in（_attr(req,"enable_*",...) 默认
按项设定），非阻断，失败不阻断主流程；遵循 ADR-005 本地优先 / 零幻觉 / 零新依赖约束。
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List

from .context import StageContext
from .stage import Stage

_log = logging.getLogger(__name__)


def _attr(req: Any, name: str, default: Any = None) -> Any:
    """安全读取请求字段（兼容 BidRequest 与 dict 入参）。"""
    if isinstance(req, dict):
        return req.get(name, default)
    return getattr(req, name, default)


# ═══════════════════════════════════════════════════════════════════════════
# T2 · 生成 LLM 核心桥接（评分硬约束注入 + 禁止编造 + 模板骨架兜底）
# ═══════════════════════════════════════════════════════════════════════════
_STUB_TOKENS = ('【', 'TODO', '待补充', '待完善', '此处填写', 'XXX', 'xxxx')


def build_generation_constraints(parse_result: Dict[str, Any]) -> List[str]:
    """T2：从招标文件解析结果构造 LLM 扩写的「硬约束清单」。

    - 逐条评分项必须响应；
    - 逐条废标红线 / 星号强制条款必须响应；
    - 零幻觉硬约束：禁止编造资质/业绩/人名/数据。
    """
    pr = parse_result or {}
    cons: List[str] = []
    for it in (pr.get('score_items') or []):
        nm = it.get('name') or it.get('title') or ''
        sc = it.get('score') or it.get('weight') or ''
        if nm:
            cons.append(f"必须逐条响应评分项「{nm}」（{sc}分），不得遗漏")
    for c in (pr.get('red_line_clauses') or []):
        txt = c.get('content') or ''
        if txt:
            cons.append(f"必须完全响应废标/无效标条款：{txt[:60]}")
    for c in (pr.get('star_clauses') or []):
        txt = c.get('content') or c.get('text') or ''
        if txt:
            cons.append(f"必须响应星号/强制条款：{txt[:60]}")
    cons.append(
        "硬约束（零幻觉）：禁止编造任何企业资质、业绩、人员姓名、证书编号或工程数据；"
        "所有承诺必须基于真实资料，无法确认的内容明确标注「待补充」而非虚构。")
    return cons


def _is_stub(text: str) -> bool:
    """仅识别显式占位桩（保守，避免误改正常正文/标题）。"""
    t = (text or '').strip()
    if not t:
        return True
    return any(tok in t for tok in _STUB_TOKENS)


@Stage.register
class LLMCoreStage(Stage):
    """T2：LLM 核心桥接（opt-in，默认关闭）。

    当 enable_llm_core=True 且配置了本地 LLM 时：将评分项/废标红线作为硬约束注入 LLM
    扩写提示，并对生成稿中显式占位桩段落做二次 LLM 精修（模板退为骨架兜底）。
    纯增量、非阻断；无 LLM 时整体跳过，回退模板生成。
    """

    name = "llm_core"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        req = ctx.req
        return (bool(_attr(req, "enable_llm_core", False))
                and ctx.llm_client is not None
                and bool(ctx.get("result_path"))
                and os.path.exists(ctx.get("result_path")))

    def run(self, ctx: StageContext) -> None:
        from docx import Document

        llm = ctx.llm_client
        parse_result = ctx.get("parse_result") or _attr(ctx.req, "parse_result") or {}
        constraints = build_generation_constraints(parse_result)

        # T2 双选项隐私方案：云端后端出网前挂载实体脱敏 Masker
        backend = getattr(getattr(llm, "config", None), "backend", "local")
        if backend == "cloud":
            # 隐私分级：商务标（报价/造价）即便选云端也严禁出网，强制降级本地并告警
            bid_section = _attr(ctx.req, "bid_section", "technical")
            bid_type = _attr(ctx.req, "bid_type", "construction")
            if bid_section == "commercial" or bid_type not in ("construction", "service"):
                _log.warning("云端后端命中商务标/非常规类型，存在报价等强隐私字段，"
                             "已拒绝出网并回退模板生成（数据不出本机）。")
                ctx.set("llm_core", {"enabled": True, "cloud_blocked": True,
                                     "reason": "commercial_privacy", "refined_count": 0})
                return
            try:
                from llm_mask import Masker
                uc = _attr(ctx.req, "user_context") or {}
                masker = Masker.from_user_context(uc)
                # 若知识库已加载且非占位，进一步丰富脱敏实体
                kb = ctx.get("kb")
                if kb is not None and getattr(kb, "is_demo", True) is False \
                        and getattr(kb, "loaded", False):
                    masker = Masker.from_entities(
                        masker._entities + Masker.from_kb(kb)._entities)
                if masker.entity_count:
                    llm.masker = masker
            except Exception as e:  # noqa: BLE001
                _log.warning("脱敏 Masker 装配失败，已按本地安全策略跳过云端扩写: %s", e)
                ctx.set("llm_core", {"enabled": True, "cloud_blocked": True,
                                     "reason": "masker_error", "refined_count": 0})
                return

        result_path = ctx.get("result_path")
        refined: List[str] = []
        try:
            doc = Document(result_path)
            for para in doc.paragraphs:
                if _is_stub(para.text):
                    title = para.text.strip()[:20] or "技术标章节"
                    new_text = llm.expand_section(title, constraints, ctx.data, parse_result)
                    if new_text:
                        para.text = new_text
                        refined.append(title)
            if refined:
                doc.save(result_path)
        except Exception as e:  # noqa: BLE001
            ctx.set("llm_core_error", str(e))
        ctx.set("llm_core", {
            "enabled": True,
            "backend": backend,
            "masked_entities": getattr(getattr(llm, "masker", None), "entity_count", 0),
            "constraints_injected": len(constraints),
            "sections_refined": refined,
            "refined_count": len(refined),
        })


def append_llm_core(orchestrator) -> None:
    orchestrator.register(LLMCoreStage())
