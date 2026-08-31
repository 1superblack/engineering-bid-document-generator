# -*- coding: utf-8 -*-
"""T5 · 三维查重 Stage（文本/结构/元数据 + 图像层可选）。

对标「标书查重合规红线」：在原有跨文档防串标（DedupStage）之外，
新增对单份生成稿的三维原创性量化：

- 文本层：精确重复率（compute_self_similarity）+ 近义重复率（SimHash 汉明）
- 结构层：章节骨架两两 Jaccard 相似度（捕捉「多章套同一模板」）
- 元数据层：文档属性/编辑痕迹泄漏检测（暗标敏感）
- 图像层（可选）：图片 OCR 自相似，依赖 pytesseract，缺失则优雅跳过

所有层纯标准库；图像层为可选依赖。opt-in（enable_dedup3d 默认 True），
非阻断，产出 ctx["dedup3d"] 供 SummaryStage（T9）披露。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from .context import StageContext
from .orchestrator import PipelineOrchestrator
from .output_paths import aux_path, aux_dir, emit_auxiliary
from .stage import Stage


def _attr(req: Any, name: str, default: Any = None) -> Any:
    if isinstance(req, dict):
        return req.get(name, default)
    return getattr(req, name, default)


class Dedup3DStage(Stage):
    """三维查重。非阻断。"""

    name = "dedup3d"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        result_path = ctx.get("result_path")
        return bool(_attr(ctx.req, "enable_dedup3d", True)) and bool(result_path) and os.path.exists(result_path)

    def run(self, ctx: StageContext) -> None:
        result_path = ctx.get("result_path")
        try:
            from dedup import compute_self_similarity_3d

            report = compute_self_similarity_3d(result_path)
        except Exception as exc:  # noqa: BLE001
            report = {"status": "error", "error": str(exc)}
            ctx.set("dedup3d", report)
            return

        md_path = None
        if report.get("status") == "ok":
            try:
                md_path = self._write_markdown(ctx, report, result_path)
            except Exception:  # noqa: BLE001
                md_path = None
        report["markdown_path"] = md_path
        ctx.set("dedup3d", report)

    def _write_markdown(self, ctx, report: Dict[str, Any], result_path: str) -> str:
        md_path = aux_path(ctx, result_path, "_三维查重.md")
        layers = report.get("layers", {})
        lines = [
            "# 三维查重报告（T5 · 原创性量化）",
            "",
            "## 各维度重复率",
            "| 维度 | 指标 | 说明 |",
            "| --- | --- | --- |",
            f"| 文本层 | {report.get('text_self_similarity')} | 精确重复句比例（含近义 SimHash {report.get('simhash_self_similarity')}） |",
            f"| 结构层 | {report.get('structure_similarity')} | 章节骨架两两相似度（捕捉套模板） |",
            f"| 元数据层 | {'泄漏' if report.get('metadata_leak') else '干净'} | 文档属性/编辑痕迹{('：' + str(report.get('metadata_fields'))) if report.get('metadata_leak') else ''} |",
            f"| 图像层 | {report.get('ocr_self_similarity') if report.get('ocr_self_similarity') is not None else '未启用'} | 图片 OCR 自相似（可选依赖） |",
            "",
            "## 结论",
            f"- 文本综合重复率：{layers.get('text')}",
            f"- 结构相似度：{layers.get('structure')}",
            "- 建议：文本/结构重复率较高时，启用差异化旋转（Differentiator）或人工改写以降低雷同风险。",
        ]
        if md_path:
            md_path.write_text("\n".join(lines), encoding="utf-8")
        return str(md_path) if md_path else None


def append_dedup3d(orchestrator: PipelineOrchestrator) -> PipelineOrchestrator:
    """把 Dedup3DStage 追加到管线末尾。"""
    orchestrator.register(Dedup3DStage())
    return orchestrator
