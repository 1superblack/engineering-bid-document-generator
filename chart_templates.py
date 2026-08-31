# -*- coding: utf-8 -*-
"""T6 · 工程图表/图纸模板生成（纯本地，零强制依赖）。

对标「技术标的脸面」——施工平面布置图 / 工艺流程图 / 项目组织机构图。
提供两类产物，按工程类型（bid_type）挑选模板：

1. 纯 SVG 矢量图（默认产出，零依赖，可直接插入支持 SVG 的查看器/转 PNG）；
2. Mermaid 文本（便于在支持 Mermaid 的 Markdown 渲染器中看图）。

甘特图另由 matplotlib 可选渲染（见 render_gantt_png），未装则回退 ASCII
（ScheduleChartStage 已负责）。

设计约束（ADR-005 / 权衡红线）：
- 纯字符串拼接生成 SVG/Mermaid，不引入图形库；
- 所有图均由同一份 project_info 数据驱动（图文联动）；
- 模板按 bid_type 切换，缺失类型回退「通用房建」模板。
"""
from __future__ import annotations

import matplotlib

matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

from typing import Any, Dict, List, Optional

# 工程类型 → 中文标签
_BIDTYPE_LABEL = {
    "construction": "房屋建筑",
    "municipal": "市政公用",
    "decor": "装饰装修",
    "landscape": "园林景观",
    "road": "公路交通",
    "service": "服务类",
}


def bidtype_label(bid_type: Optional[str]) -> str:
    return _BIDTYPE_LABEL.get(bid_type, "房屋建筑")


# ────────────────────────────────────────────────────────────
# 施工平面布置图（SVG，按工程类型挑选区块布局）
# ────────────────────────────────────────────────────────────
def site_layout_svg(bid_type: Optional[str] = "construction",
                    project: Optional[Dict[str, Any]] = None) -> str:
    """生成施工平面布置图 SVG（通用网格 + 类型化区块标签）。"""
    p = project or {}
    name = (p.get("name") or "本工程")
    label = bidtype_label(bid_type)
    # 区块：按类型给出不同的功能分区文字
    if bid_type == "municipal":
        blocks = [("施工围挡", 60, 60), ("管线作业面", 300, 60),
                  ("材料堆场", 60, 300), ("临时交通导改", 300, 300)]
    elif bid_type in ("decor", "landscape"):
        blocks = [("施工作业区", 60, 60), ("材料仓储", 300, 60),
                  ("成品保护区", 60, 300), ("垃圾清运点", 300, 300)]
    else:  # construction 通用房建
        blocks = [("办公生活区", 60, 60), ("材料堆场", 300, 60),
                  ("主体施工区", 60, 300), ("加工棚/机械", 300, 300)]
    rects = "\n".join(
        f'<rect x="{x}" y="{y}" width="200" height="120" rx="8" '
        f'fill="#e8f0fe" stroke="#4285f4" stroke-width="2"/>'
        f'<text x="{x+100}" y="{y+65}" text-anchor="middle" '
        f'font-size="18" fill="#1a237e">{t}</text>'
        for t, x, y in blocks
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 480" width="560" height="480">
  <rect x="0" y="0" width="560" height="480" fill="#ffffff" stroke="#333" stroke-width="3"/>
  <text x="280" y="34" text-anchor="middle" font-size="20" font-weight="bold" fill="#202124">{name} · 施工总平面布置图（{label}）</text>
  {rects}
  <line x1="280" y1="40" x2="280" y2="440" stroke="#bbb" stroke-dasharray="6 4"/>
  <line x1="20" y1="240" x2="540" y2="240" stroke="#bbb" stroke-dasharray="6 4"/>
  <text x="280" y="465" text-anchor="middle" font-size="13" fill="#666">临时道路 · 消防通道 · 水电接入点详见施工组织设计</text>
</svg>'''


# ────────────────────────────────────────────────────────────
# 工艺/施工流程图（SVG，通用工序链）
# ────────────────────────────────────────────────────────────
def process_flow_svg(bid_type: Optional[str] = "construction") -> str:
    """生成工艺流程图 SVG（横向工序节点 + 箭头）。"""
    label = bidtype_label(bid_type)
    steps = ["施工准备", "测量放线", "基础/土方", "主体结构",
             "装饰装修", "机电安装", "竣工验收"]
    if bid_type == "municipal":
        steps = ["导改围挡", "管线探测", "沟槽开挖", "管道敷设",
                 "回填压实", "路面恢复", "交工验收"]
    elif bid_type in ("decor", "landscape"):
        steps = ["深化设计", "样板引路", "基层施工", "面层施工",
                 "细部收口", "成品保护", "竣工验收"]
    boxes = []
    arrows = []
    x0, y, w, h, gap = 20, 220, 70, 50, 18
    for i, s in enumerate(steps):
        x = x0 + i * (w + gap)
        boxes.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
            f'fill="#e6f4ea" stroke="#34a853" stroke-width="2"/>'
            f'<text x="{x+w/2}" y="{y+h/2+5}" text-anchor="middle" '
            f'font-size="11" fill="#1b5e20">{s}</text>')
        if i < len(steps) - 1:
            ax = x + w
            arrows.append(
                f'<line x1="{ax}" y1="{y+h/2}" x2="{ax+gap}" y2="{y+h/2}" '
                f'stroke="#555" stroke-width="2"/>'
                f'<polygon points="{ax+gap},{y+h/2-4} {ax+gap+6},{y+h/2} {ax+gap},{y+h/2+4}" fill="#555"/>')
    total_w = x0 + len(steps) * (w + gap)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} 300" width="{total_w}" height="300">
  <text x="{total_w/2}" y="40" text-anchor="middle" font-size="18" font-weight="bold" fill="#202124">工艺/施工流程图（{label}）</text>
  {"".join(boxes)}
  {"".join(arrows)}
</svg>'''


# ────────────────────────────────────────────────────────────
# 项目组织机构图（SVG，树状）
# ────────────────────────────────────────────────────────────
def org_chart_svg(project: Optional[Dict[str, Any]] = None) -> str:
    """生成项目组织机构图 SVG（项目经理 → 五大负责人）。"""
    p = project or {}
    pm = (p.get("pm_name") or "项目经理")
    nodes = [
        (pm, 300, 40, "#4285f4"),
        ("技术负责人", 80, 160, "#34a853"),
        ("生产/施工负责人", 240, 160, "#34a853"),
        ("质量负责人", 400, 160, "#34a853"),
        ("安全负责人", 560, 160, "#34a853"),
        ("商务/合同负责人", 720, 160, "#34a853"),
    ]
    boxes = []
    lines = []
    rx, ry, rw, rh = 300, 40, 160, 44
    for i, (t, x, y, c) in enumerate(nodes):
        boxes.append(
            f'<rect x="{x}" y="{y}" width="150" height="{rh}" rx="8" '
            f'fill="{c}" opacity="0.15" stroke="{c}" stroke-width="2"/>'
            f'<text x="{x+75}" y="{y+rh/2+5}" text-anchor="middle" '
            f'font-size="13" fill="#202124">{t}</text>')
        if i > 0:
            lines.append(
                f'<line x1="{rx+75}" y1="{ry+rh}" x2="{x+75}" y2="{y}" '
                f'stroke="#888" stroke-width="2"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 240" width="880" height="240">
  <text x="440" y="28" text-anchor="middle" font-size="16" font-weight="bold" fill="#202124">项目组织机构图</text>
  {"".join(lines)}
  {"".join(boxes)}
</svg>'''


# ────────────────────────────────────────────────────────────
# Mermaid 文本（便于 Markdown 渲染）
# ────────────────────────────────────────────────────────────
def mermaid_process_flow(bid_type: Optional[str] = "construction") -> str:
    label = bidtype_label(bid_type)
    if bid_type == "municipal":
        steps = ["导改围挡", "管线探测", "沟槽开挖", "管道敷设", "回填压实", "路面恢复", "交工验收"]
    elif bid_type in ("decor", "landscape"):
        steps = ["深化设计", "样板引路", "基层施工", "面层施工", "细部收口", "成品保护", "竣工验收"]
    else:
        steps = ["施工准备", "测量放线", "基础土方", "主体结构", "装饰装修", "机电安装", "竣工验收"]
    body = "\n".join(f"    {i+1}-->|{s}|{i+2}" for i, s in enumerate(steps[:-1]))
    return f"flowchart LR\n    subgraph {label}工艺流\n{body}\n    end"


def mermaid_org_chart(project: Optional[Dict[str, Any]] = None) -> str:
    p = project or {}
    pm = (p.get("pm_name") or "项目经理")
    return (
        "flowchart TB\n"
        f"    PM[{pm}] --> T[技术负责人]\n"
        f"    PM --> P[生产施工负责人]\n"
        f"    PM --> Q[质量负责人]\n"
        f"    PM --> S[安全负责人]\n"
        f"    PM --> B[商务合同负责人]"
    )


# ────────────────────────────────────────────────────────────
# matplotlib 真·甘特图（可选依赖，未装返回 None）
# ────────────────────────────────────────────────────────────
def render_gantt_png(phases: List[Dict[str, Any]], out_path: str,
                     duration: int = 0) -> Optional[str]:
    """用 matplotlib 渲染真实甘特图 PNG；matplotlib 缺失则优雅返回 None。

    phases: [{'name','start','end', 'days'}]
    """
    try:
        import matplotlib  # type: ignore
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.patches import Patch  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        fig, ax = plt.subplots(figsize=(10, max(2.5, len(phases) * 0.7)))
        for i, ph in enumerate(phases):
            start = ph.get("start", 1)
            days = max(1, ph.get("days", 1))
            ax.barh(i, days, left=start - 1, height=0.6, color="#4285f4", alpha=0.85)
            ax.text(start - 1, i, f" {ph.get('name','')}", va="center", fontsize=9)
        ax.set_yticks(range(len(phases)))
        ax.set_yticklabels([ph.get("name", "") for ph in phases])
        ax.invert_yaxis()
        ax.set_xlabel("工期（天）")
        ax.set_title("施工进度计划甘特图")
        ax.grid(axis="x", linestyle=":", alpha=0.5)
        fig.tight_layout()
        fig.savefig(out_path, dpi=110)
        plt.close(fig)
        return out_path
    except Exception:  # noqa: BLE001
        return None
