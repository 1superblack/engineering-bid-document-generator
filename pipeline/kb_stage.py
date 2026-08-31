# -*- coding: utf-8 -*-
"""T7 · 知识库 RAG + 零幻觉事实核查 Stage（opt-in，默认关闭）。

- 加载本地知识库（user_knowledge_base.json 或 knowledge_base_path）；
- 对生成稿做语义检索（BM25），产出可注入提示的「真实素材块」（与 T2 联动）；
- 生成后对照知识库做事实核查，标记「疑似编造资质/业绩/人名/编号」；
- 零幻觉硬约束：素材只来自知识库，绝不自动写回（回流需人工确认）。

纯 python，零强制依赖；enable_kb_rag 默认 False（ADR-005：可选资产不进默认路径）。
非阻断；知识库缺失时优雅降级为 status='no_kb'。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from .context import StageContext
from .orchestrator import PipelineOrchestrator
from .output_paths import aux_path, aux_dir, emit_auxiliary
from .stage import Stage

_DEFAULT_KB = "user_knowledge_base.json"


def _attr(req: Any, name: str, default: Any = None) -> Any:
    if isinstance(req, dict):
        return req.get(name, default)
    return getattr(req, name, default)


class FactCheckStage(Stage):
    """知识库 RAG + 零幻觉事实核查。非阻断。"""

    name = "kb_factcheck"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        result_path = ctx.get("result_path")
        return bool(_attr(ctx.req, "enable_kb_rag", False)) and bool(result_path) and os.path.exists(result_path)

    def _load_kb(self, ctx: StageContext) -> Optional[Any]:
        try:
            from knowledge_base import KnowledgeBase
        except Exception:  # noqa: BLE001
            return None
        skill_root = str(Path(__file__).resolve().parents[1])
        kb_path = _attr(ctx.req, "knowledge_base_path") or _DEFAULT_KB
        # 候选顺序：显式文件 → 显式目录 → kb_sources 目录 → 默认占位文件
        candidates = [kb_path,
                      os.path.join(skill_root, kb_path),
                      os.path.join(skill_root, "kb_sources")]
        for c in candidates:
            if c and os.path.isdir(c):
                return KnowledgeBase.load_dir(c)
            if c and os.path.isfile(c):
                return KnowledgeBase.load(c)
        return KnowledgeBase([])

    def run(self, ctx: StageContext) -> None:
        result_path = ctx.get("result_path")
        kb = self._load_kb(ctx)
        if kb is None or not kb.loaded:
            ctx.set("kb_rag", {"status": "no_kb", "retrieved_count": 0, "retrieved": []})
            ctx.set("kb_factcheck", {"status": "no_kb", "kb_loaded": False,
                                     "flagged_count": 0, "flagged": []})
            return
        # 占位脚手架：声明式核查不告警（D4），仅做检索展示
        if kb.is_demo:
            ctx.set("kb_rag", {"status": "demo_kb", "entry_count": len(kb.entries),
                               "retrieved_count": 0, "retrieved": []})
            ctx.set("kb_factcheck", {"status": "demo_kb", "kb_loaded": True,
                                     "kb_is_demo": True, "flagged_count": 0, "flagged": [],
                                     "note": "知识库为占位脚手架，未配置真实素材，零幻觉核查已自动停用"})
            return

        # 文档全文（供检索/核查）
        doc_text = ""
        try:
            from checker.risk_library import _extract_doc_text
            doc_text = _extract_doc_text(result_path) or ""
        except Exception:  # noqa: BLE001
            doc_text = ""

        # 1) 检索：把生成稿作为查询，取 top-k 真实素材（与 T2 联动）
        retrieved = kb.retrieve(doc_text[:2000], topk=8)
        from knowledge_base import extract_kb_for_generation
        inject_block = extract_kb_for_generation(kb, doc_text[:2000], topk=8)

        # 2) 事实核查：声明式相对核查（仅与 KB 声明真实信息矛盾才告警）
        flagged = kb.fact_check(doc_text)

        ctx.set("kb_rag", {
            "status": "ok",
            "entry_count": len(kb.entries),
            "retrieved_count": len(retrieved),
            "retrieved": [{"type": r.get("type"), "text": r.get("text"), "score": r.get("score")}
                          for r in retrieved],
            "inject_block": inject_block,
        })
        ctx.set("kb_factcheck", {
            "status": "ok",
            "kb_loaded": True,
            "kb_is_demo": False,
            "flagged_count": len(flagged),
            "flagged": flagged,
        })
        # 若有疑似编造，写一份告警报告
        if flagged:
            md = self._write_markdown(ctx, flagged, result_path)
            ctx.set("kb_factcheck_report", md)

    def _write_markdown(self, ctx, flagged: list, result_path: str) -> Optional[str]:
        try:
            md = aux_path(ctx, result_path, "_零幻觉核查.md")
            lines = ["# 零幻觉事实核查（T7 · 与知识库声明不符告警）", "",
                     "> 以下具体标识出现在生成稿，但与本地知识库**声明真实信息不符**，疑似编造。",
                     "> 请核对真实资料后补充/修正知识库，或将表述改为「待补充」。", ""]
            for i, f in enumerate(flagged, 1):
                lines.append(f"{i}. 【{f.get('kind')}】{f.get('value')} —— {f.get('note')}")
            if md:
                md.write_text("\n".join(lines), encoding="utf-8")
                return str(md)
            return None
        except Exception:  # noqa: BLE001
            return None


def append_kb_factcheck(orchestrator: PipelineOrchestrator) -> PipelineOrchestrator:
    """把 FactCheckStage 追加到管线末尾。"""
    orchestrator.register(FactCheckStage())
    return orchestrator
