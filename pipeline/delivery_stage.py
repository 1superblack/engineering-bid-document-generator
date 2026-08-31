# -*- coding: utf-8 -*-
"""电子标书输出适配器（PDCA-Act 交付物，修订C 实化版）。

本地优先架构下，CA 签章必须由用户在本机持有，工具无法代签；但可：
1. 检测本机 PDF 转换器（libreoffice / soffice / Word+docx2pdf），可用则 docx→PDF；
2. 始终产出结构化「交付清单」Markdown：列出成稿、体积、平台格式要求、
   CA 签章提示、上传前自检清单，便于用户对照各交易平台上传规范。

插件仍是 opt-in：默认开启；非阻断，无 PDF 转换器时仅产出结构化交付清单
（manifest_only），有转换器才生成 PDF。显式传 enable_delivery=False 即关闭。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

from .context import StageContext
from .orchestrator import PipelineOrchestrator
from .output_paths import aux_path, aux_dir, emit_auxiliary
from .registry import register_stage
from .stage import Stage


def _sha256(path: str) -> Optional[str]:
    """源文件 SHA256（审计溯源，数据不出本机）。失败返回 None。"""
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:  # noqa: BLE001
        return None


def _flag(req: Any, name: str, default: Any = False) -> Any:
    if isinstance(req, dict):
        return req.get(name, default)
    return getattr(req, name, default)


def _find_pdf_converter() -> Optional[Tuple[str, Optional[str]]]:
    """返回 (kind, exe) 或 None。"""
    for exe in ('libreoffice', 'soffice', 'libreoffice.exe', 'soffice.exe'):
        p = shutil.which(exe)
        if p:
            return ('libreoffice', p)
    for cand in (
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    ):
        if os.path.exists(cand):
            return ('libreoffice', cand)
    try:
        import docx2pdf  # noqa: F401
        return ('docx2pdf', None)
    except Exception:
        return None


class DeliveryStage(Stage):
    """电子标书输出适配器。非阻断。"""

    name = "delivery"
    blocking = False

    def should_run(self, ctx: StageContext) -> bool:
        # 默认开启：非阻断，无 PDF 转换器时仍产出结构化交付清单（manifest_only）
        return bool(_flag(ctx.req, "enable_delivery", True))

    def run(self, ctx: StageContext) -> None:
        result_path = ctx.get("result_path")
        if not result_path or not os.path.exists(result_path):
            ctx.set("delivery", {"status": "skipped", "note": "无成稿路径"})
            return
        if not emit_auxiliary(ctx):
            ctx.set("delivery", {"status": "skipped",
                                 "note": "emit_auxiliary=False，不落盘辅助产物"})
            return

        # 平台格式精准提示（来自资产层 platform_formats，可选；缺则回退通用提示）
        _assets = ctx.get('assets') or {}
        _pf = _assets.get('platform_formats') if isinstance(_assets, dict) else None
        platform = _flag(ctx.req, 'bid_platform') or ''
        fmt = None
        if isinstance(_pf, dict):
            _fmts = _pf.get('formats', _pf)
            fmt = _fmts.get(platform) if platform else None

        conv = _find_pdf_converter()
        pdf_path = None
        if conv:
            kind, exe = conv
            try:
                if kind == 'libreoffice' and exe:
                    out_dir = str(aux_dir(result_path, ctx))
                    subprocess.run(
                        [exe, '--headless', '--convert-to', 'pdf',
                         '--outdir', out_dir, result_path],
                        check=True, timeout=120,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    cand = aux_dir(result_path, ctx) / (Path(result_path).stem + '.pdf')
                    pdf_path = str(cand) if cand.exists() else None
                elif kind == 'docx2pdf':
                    import docx2pdf
                    pdf_path = str(aux_dir(result_path, ctx) / (Path(result_path).stem + '.pdf'))
                    docx2pdf.convert(result_path, pdf_path)
            except Exception as e:  # noqa: BLE001
                pdf_path = None
                ctx.set("delivery_error", f"{type(e).__name__}: {e}")

        pdf_status = ("已转换(PDF)" if pdf_path
                      else "PDF转换器未找到（建议安装 LibreOffice，或本机用 Word 另存为 PDF）")

        size = os.path.getsize(result_path)
        generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        source_sha256 = _sha256(result_path)
        if fmt:
            platform_format_note = (
                f"平台格式：{fmt.get('name', '')}（{fmt.get('platform', '')}）。"
                f"需用{fmt.get('client', '')}：{fmt.get('requires', '')}。"
                f"提示：{fmt.get('tip', '')}")
            platform_matched = platform
        else:
            platform_format_note = (
                "各交易平台要求加密专格式（如 .etnd / .XYTF / .BTBJ / .lytf），"
                "须用对应「投标文件编制客户端」导入本 PDF/Word 并 CA 签章后上传；"
                "工具不代持 CA 证书。")
            platform_matched = None
        manifest = {
            "status": "delivered" if pdf_path else "manifest_only",
            "source_docx": result_path,
            "pdf": pdf_path,
            "pdf_status": pdf_status,
            "size_bytes": size,
            "size_kb": round(size / 1024, 1),
            "generated_at": generated_at,
            "source_sha256": source_sha256,
            "platform_matched": platform_matched,
            "platform_format_note": platform_format_note,
            "ca_note": (
                "上传前须用本单位 CA 数字证书在平台客户端完成签章与加密；"
                "同一项目仅可用同一把 CA，否则解密失败。"),
            "checklist": [
                "逐页核对★实质性条款已响应（漏 1 条即可能废标）",
                "签字/盖章/骑缝章/密封/正副本份数符合招标文件格式",
                "暗标项目清除企业 LOGO、人员姓名、联系方式",
                "PDF 每页大小/总大小符合平台限制（如双层 PDF ≤40KB/页）",
            ],
        }
        ctx.set("delivery", manifest)
        try:
            self._write_manifest(manifest, result_path, ctx)
        except Exception:  # noqa: BLE001
            pass

    def _write_manifest(self, manifest, result_path, ctx):
        md = aux_path(ctx, result_path, '_交付清单.md')
        lines = ["# 电子标书交付清单（PDCA-Act 自动生成）", ""]
        lines.append(f"- 源文件：{manifest['source_docx']}")
        lines.append(f"- 生成时间：{manifest['generated_at']}")
        lines.append(f"- 源文件 SHA256：{manifest['source_sha256'] or '（计算失败）'}")
        lines.append(f"- PDF：{manifest['pdf'] or '（未生成）'} —— {manifest['pdf_status']}")
        lines.append(f"- 体积：{manifest['size_kb']} KB")
        lines.append(f"- 平台格式：{manifest['platform_format_note']}")
        lines.append(f"- CA 签章：{manifest['ca_note']}")
        lines.append("")
        lines.append("## 上传前自检清单")
        for c in manifest['checklist']:
            lines.append(f"- [ ] {c}")
        if md:
            md.write_text('\n'.join(lines), encoding='utf-8')
            manifest['manifest_path'] = str(md)


def register_delivery() -> None:
    """把 DeliveryStage 显式登记进注册表（插件 opt-in）。幂等。"""
    register_stage("delivery")(DeliveryStage)
    return None


def append_delivery(orchestrator: PipelineOrchestrator) -> PipelineOrchestrator:
    """把 DeliveryStage 追加到已有管线的末尾（需先 register_delivery）。"""
    register_delivery()
    orchestrator.register(DeliveryStage())
    return orchestrator
