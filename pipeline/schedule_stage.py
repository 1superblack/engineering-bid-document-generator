# -*- coding: utf-8 -*-
"""施工进度横道图 Stage（PDCA-Act 交付物，修订C 图表配套）。

对标标猪侠「自动配套工程图表（横道图 / 工程附表）」的差异化能力：
本地优先、零外部依赖（不引入 matplotlib），用 Unicode 方块渲染横道图，
并产出 Markdown 进度计划表（工序 / 工期 / 起止），作为技术标可交付附件。

纯规则 + 数据，非阻断，opt-in（默认启用 enable_schedule_chart）。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from .context import StageContext
from .orchestrator import PipelineOrchestrator
from .output_paths import aux_path, aux_dir, emit_auxiliary
from .stage import Stage

# 典型施工阶段比例（合计 100%）；可按行业在资产层扩展
_DEFAULT_PHASES = [
    ("施工准备与进场", 0.08),
    ("基础与土方工程", 0.22),
    ("主体结构工程", 0.35),
    ("装饰装修与安装", 0.25),
    ("竣工验收与清理", 0.10),
]


def _attr(req: Any, name: str, default: Any = None) -> Any:
    if isinstance(req, dict):
        return req.get(name, default)
    return getattr(req, name, default)


class ScheduleChartStage(Stage):
    """施工进度横道图。非阻断。"""

    name = "schedule_chart"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        req = ctx.req
        return bool(_attr(req, "enable_schedule_chart", True)) and bool(_attr(req, "duration"))

    def run(self, ctx: StageContext) -> None:
        req = ctx.req
        duration = int(_attr(req, "duration") or 0)
        if duration <= 0:
            ctx.set("schedule_chart", {"status": "skipped", "note": "工期为 0"})
            return

        phases = self._build_phases(duration, self._resolve_phases(ctx))
        chart_text = self._render(duration, phases)
        table_md = self._render_table(duration, phases)

        result_path = ctx.get("result_path")
        md_path = None
        if result_path:
            try:
                md_path = aux_path(ctx, result_path, "_施工进度横道图.md")
                lines = [
                    "# 施工进度横道图（PDCA-Act 自动生成）",
                    "",
                    f"- 总工期：{duration} 天",
                    "",
                    "```",
                    chart_text,
                    "```",
                    "",
                    "## 进度计划表",
                    "",
                    "| 工序 | 计划工期(天) | 开始(第N天) | 结束(第N天) |",
                    "| --- | --- | --- | --- |",
                ]
                for p in phases:
                    lines.append(f"| {p['name']} | {p['days']} | {p['start']} | {p['end']} |")
                if md_path is not None:
                    Path(md_path).write_text("\n".join(lines), encoding="utf-8")
            except Exception:  # noqa: BLE001
                md_path = None

        ctx.set("schedule_chart", {
            "status": "ok",
            "duration": duration,
            "phases": phases,
            "chart": chart_text,
            "markdown_path": md_path,
        })

    def _resolve_phases(self, ctx: StageContext) -> List[tuple]:
        """阶段比例来源：资产层 schedule_phases > 内置默认；自动归一化。

        资产层覆盖即插即用、可逆：删除资产即回退默认；比例合计非 1 也会归一化，
        避免坏数据导致横道图失真。
        """
        _assets = ctx.get('assets') or {}
        sp = _assets.get('schedule_phases') if isinstance(_assets, dict) else None
        phases = None
        if isinstance(sp, dict):
            _ph = sp.get('phases') or []
            _phases = [(p.get('name'), float(p.get('ratio', 0)))
                       for p in _ph if p.get('name')]
            if _phases:
                phases = _phases
        if not phases:
            phases = list(_DEFAULT_PHASES)
        total = sum(r for _, r in phases)
        if total > 0:
            phases = [(n, r / total) for n, r in phases]
        return phases

    def _build_phases(self, duration: int, src_phases: List[tuple]) -> List[Dict[str, Any]]:
        phases: List[Dict[str, Any]] = []
        cursor = 1
        last = len(src_phases) - 1
        for i, (name, ratio) in enumerate(src_phases):
            # 最后一段吃掉舍入余数，保证合计 == duration
            if i == last:
                days = duration - (cursor - 1)
            else:
                days = max(1, round(duration * ratio))
            end = cursor + days - 1
            phases.append({"name": name, "ratio": ratio,
                           "days": days, "start": cursor, "end": end})
            cursor = end + 1
        return phases

    def _render(self, duration: int, phases: List[Dict[str, Any]], width: int = 40) -> str:
        lines = []
        for p in phases:
            filled = round(width * p["days"] / duration)
            bar = "█" * filled
            lines.append(f"{p['name']:<10} |{bar:<{width}}| {p['start']:>3}-{p['end']:<3}天")
        return "\n".join(lines)

    def _render_table(self, duration: int, phases: List[Dict[str, Any]]) -> str:
        return "\n".join(
            f"{p['name']}: {p['days']}天 ({p['start']}-{p['end']})" for p in phases)


def append_schedule_chart(orchestrator: PipelineOrchestrator) -> PipelineOrchestrator:
    """把 ScheduleChartStage 追加到管线末尾。"""
    orchestrator.register(ScheduleChartStage())
    return orchestrator
