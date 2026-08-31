# -*- coding: utf-8 -*-
"""ADR-008：辅助产物集中输出路径策略。

背景
----
此前每个交付物 Stage 都把辅助报告（.md）/PDF/图表等直接写到主文档所在目录
（result_path.parent），导致用户指定的 output_path（如桌面）被 ~15 个辅助文件淹没。

策略（默认，可逆）
----------------
- 主 docx **仍写到用户指定的 result_path**（桌面只留这一个文件）；
- 其余辅助产物统一归集到同名子文件夹 ``<主文档名>_交付物/``，与主文档同父目录；
- 可选硬开关 ``emit_auxiliary=False``：完全不落盘辅助文件（仍保留在程序返回结果里）。

所有辅助写盘都经由本模块，路径策略单一可控、易回滚。新增 Stage 写盘请统一调用
``aux_path`` / ``aux_dir``，不要再 ``out.with_name(...)`` 直接落主文档目录。
"""
from __future__ import annotations

from pathlib import Path


def _flag(req, name, default=False):
    if isinstance(req, dict):
        return req.get(name, default)
    return getattr(req, name, default) if req is not None else default


def emit_auxiliary(ctx) -> bool:
    """是否落盘辅助产物。默认 True；emit_auxiliary=False 时仅生成主 docx。"""
    if ctx is None:
        return True
    return _flag(getattr(ctx, "req", None), "emit_auxiliary", True)


def aux_dir(result_path, ctx=None) -> Path:
    """辅助产物归集目录：<主文档父目录>/<主文档名>_交付物/（自动创建）。"""
    p = Path(result_path)
    d = p.parent / (p.stem + "_交付物")
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        pass
    return d


def aux_path(ctx, result_path, suffix):
    """计算辅助产物路径；emit_auxiliary=False 时返回 None（不落盘）。

    suffix 形如 ``_废标风险自检报告.md``（含前导下划线与扩展名）。
    """
    if not emit_auxiliary(ctx):
        return None
    return aux_dir(result_path, ctx) / (Path(result_path).stem + suffix)
