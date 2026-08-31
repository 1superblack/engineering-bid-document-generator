# -*- coding: utf-8 -*-
"""T6 · 工程图表/图纸生成 Stage（纯本地 + matplotlib 可选）。

在 ScheduleChartStage（ASCII 横道图）基础上补充「技术标的脸面」：
- matplotlib 真·甘特图 PNG（可选依赖，未装则跳过，ASCII 已保底）；
- 施工平面布置图 / 工艺流程图 / 项目组织机构图（纯 SVG，按 bid_type 选模板）；
- Mermaid 文本索引（便于 Markdown 渲染看图）。

图文联动：甘特图直接复用 ScheduleChartStage 已计算的 phases，保证与 ASCII 横道图一致。
所有产物为独立交付文件（SVG/PNG/MD），不强行嵌入 docx（嵌入 SVG 复杂度高，
留给桌面端扩展缝）；通过总览报告与文件清单呈现。

opt-in（enable_charts 默认 True），非阻断，失败不影响主流程。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .context import StageContext
from .orchestrator import PipelineOrchestrator
from .output_paths import aux_path, aux_dir, emit_auxiliary
from .stage import Stage


def _attr(req: Any, name: str, default: Any = None) -> Any:
    if isinstance(req, dict):
        return req.get(name, default)
    return getattr(req, name, default)


class ChartStage(Stage):
    """工程图表/图纸生成。非阻断。"""

    name = "charts"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        result_path = ctx.get("result_path")
        has_input = bool(_attr(ctx.req, "duration")) or (ctx.get("schedule_chart") or {}).get("phases")
        return bool(_attr(ctx.req, "enable_charts", True)) and bool(result_path) and bool(has_input)

    def _resolve_phases(self, ctx: StageContext, duration: int) -> List[Dict[str, Any]]:
        sc = ctx.get("schedule_chart") or {}
        phases = sc.get("phases")
        if phases:
            return phases
        # 回退：自行按比例构建（与 ScheduleChartStage 同算法）
        from .schedule_stage import _DEFAULT_PHASES

        src = list(_DEFAULT_PHASES)
        total = sum(r for _, r in src)
        if total > 0:
            src = [(n, r / total) for n, r in src]
        cursor = 1
        out: List[Dict[str, Any]] = []
        last = len(src) - 1
        for i, (name, ratio) in enumerate(src):
            if i == last:
                days = duration - (cursor - 1)
            else:
                days = max(1, round(duration * ratio))
            if days <= 0:
                break
            end = cursor + days - 1
            out.append({"name": name, "days": days, "start": cursor, "end": end})
            cursor = end + 1
        return out

    def run(self, ctx: StageContext) -> None:
        result_path = ctx.get("result_path")
        req = ctx.req
        bid_type = _attr(req, "bid_type", "construction")
        duration = int(_attr(req, "duration") or 0)
        project = ctx.data or {}
        phases = self._resolve_phases(ctx, duration)

        base = Path(result_path)
        out_dir = aux_dir(result_path, ctx)
        out: Dict[str, Any] = {"charts": [], "mermaid": {}}

        # 1) matplotlib 真·甘特图（可选）
        try:
            from chart_templates import render_gantt_png

            png = out_dir / (base.stem + "_施工进度甘特图.png")
            p = render_gantt_png(phases, str(png), duration)
            if p:
                out["gantt_png"] = str(png)
                out["charts"].append(png.name)
        except Exception:  # noqa: BLE001
            pass

        # 2) 纯 SVG 图纸模板（按工程类型）
        try:
            from chart_templates import (
                site_layout_svg, process_flow_svg, org_chart_svg,
                mermaid_process_flow, mermaid_org_chart, bidtype_label,
            )

            site = out_dir / (base.stem + "_施工平面布置图.svg")
            site.write_text(site_layout_svg(bid_type, project), encoding="utf-8")
            flow = out_dir / (base.stem + "_工艺流程图.svg")
            flow.write_text(process_flow_svg(bid_type), encoding="utf-8")
            org = out_dir / (base.stem + "_项目组织机构图.svg")
            org.write_text(org_chart_svg(project), encoding="utf-8")
            out["charts"].extend([site.name, flow.name, org.name])
            out["mermaid"]["process_flow"] = mermaid_process_flow(bid_type)
            out["mermaid"]["org_chart"] = mermaid_org_chart(project)
            out["bidtype"] = bidtype_label(bid_type)
        except Exception as exc:  # noqa: BLE001
            out["svg_error"] = str(exc)

        # 3) Mermaid 索引 MD
        try:
            idx = out_dir / (base.stem + "_工程图表索引.md")
            lines = [
                "# 工程图表索引（T6 · 自动生成）",
                "",
                f"- 工程类型：{out.get('bidtype', bidtype_label(bid_type))}",
                f"- 总工期：{duration} 天",
                "",
                "## 矢量图纸（SVG，可直接查看/转 PNG）",
            ]
            for c in out.get("charts", []):
                lines.append(f"- {c}")
            if out.get("gantt_png"):
                lines.append(f"- {Path(out['gantt_png']).name}（matplotlib 真·甘特图）")
            lines += [
                "",
                "## 工艺流程图（Mermaid）",
                "```mermaid",
                out.get("mermaid", {}).get("process_flow", ""),
                "```",
                "",
                "## 项目组织机构图（Mermaid）",
                "```mermaid",
                out.get("mermaid", {}).get("org_chart", ""),
                "```",
            ]
            idx.write_text("\n".join(lines), encoding="utf-8")
            out["index_md"] = str(idx)
        except Exception:  # noqa: BLE001
            pass

        ctx.set("charts", out)


def append_charts(orchestrator: PipelineOrchestrator) -> PipelineOrchestrator:
    """把 ChartStage 追加到管线末尾。"""
    orchestrator.register(ChartStage())
    return orchestrator
