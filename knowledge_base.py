# -*- coding: utf-8 -*-
"""T7 · 本地知识库检索 + 零幻觉事实核查（纯 python，零强制依赖）。

背景（优化清单 T7 / ADR-005）：
企业画像删除后，零幻觉护城河变薄。本模块把 user_knowledge_base.json 这类
「真实企业资料」提升为可检索资产：生成时语义检索注入 prompt（与 T2 联动），
生成后对照知识库做事实核查，硬性拦截「编造资质/业绩/人名/编号」。

设计约束（权衡红线）：
- 纯标准库 BM25（字符 bi-gram），不强制 embedding 模型；
- 可选资产，不进默认路径（enable_kb_rag 默认 False）；
- 所有素材必须真实；回流需人工确认（本模块只检索/核查，不自动写回）。
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _char_bigrams(text: str) -> List[str]:
    t = (text or "").strip()
    if len(t) < 2:
        return [t] if t else []
    return [text[i:i + 2] for i in range(len(text) - 1)]


def _flatten(d: Any, prefix: str = "") -> List[Dict[str, Any]]:
    """把知识库 JSON 拍平为可检索条目。"""
    entries: List[Dict[str, Any]] = []
    if isinstance(d, dict):
        for k, v in d.items():
            if k.startswith("_"):
                continue
            entries += _flatten(v, k)
    elif isinstance(d, list):
        for i, it in enumerate(d):
            if isinstance(it, dict):
                name = it.get("name") or it.get("role") or f"{prefix}_{i}"
                parts = [str(it.get(x, "")) for x in
                         ("name", "role", "cert", "cert_no", "title", "major",
                          "amount", "scale", "year", "model", "brand", "desc", "description")]
                text = "；".join([p for p in parts if p])
                if text:
                    entries.append({"id": f"{prefix}:{name}", "type": prefix,
                                    "name": name, "text": text})
            else:
                if it:
                    entries.append({"id": f"{prefix}:{i}", "type": prefix,
                                    "name": str(it), "text": str(it)})
    else:
        if d not in (None, "", []):
            entries.append({"id": prefix, "type": prefix,
                            "name": str(d), "text": str(d)})
    return entries


# 声明式核查：claim 模式 → 知识库条目 type（声明"什么是真实的"才核对）
_KIND_TO_TYPE: Dict[str, str] = {
    "资质编号": "qualifications",
    "项目经理": "key_personnel",
    "业绩项目": "similar_projects",
    "人员证书号": "key_personnel",
}


def _chunk_text(text: str, maxlen: int = 220) -> List[str]:
    """把长文本按空行/句切分为可检索块（纯标准库）。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    chunks: List[str] = []
    for p in paras:
        if len(p) <= maxlen:
            chunks.append(p)
            continue
        # 超长段落按句（。！？；）再切
        buf = ""
        for seg in re.split(r"(?<=[。！？；])", p):
            if len(buf) + len(seg) > maxlen and buf:
                chunks.append(buf.strip())
                buf = seg
            else:
                buf += seg
        if buf.strip():
            chunks.append(buf.strip())
    return [c for c in chunks if len(c) >= 4]


class KnowledgeBase:
    """本地知识库：加载 + BM25 检索 + 事实核查。"""

    def __init__(self, entries: Optional[List[Dict[str, Any]]] = None):
        self.entries: List[Dict[str, Any]] = entries or []
        self._df: Dict[str, int] = {}
        self._doc_tokens: List[List[str]] = []
        self._by_type: Dict[str, List[Dict[str, Any]]] = {}
        self._build_index()

    # ── 加载 ──────────────────────────────────────────────
    @classmethod
    def load(cls, path: str) -> "KnowledgeBase":
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:  # noqa: BLE001
            return cls([])
        entries = _flatten(data)
        return cls(entries)

    @classmethod
    def load_dir(cls, dirpath: str,
                 exts: Tuple[str, ...] = (".txt", ".md", ".json")) -> "KnowledgeBase":
        """递归读取目录下的真实素材（.txt/.md/.json），分块 BM25 索引。

        纯标准库，零新依赖；JSON 走 _flatten，文本走 _chunk_text。
        """
        entries: List[Dict[str, Any]] = []
        if not os.path.isdir(dirpath):
            return cls([])
        for root, _, files in os.walk(dirpath):
            for f in sorted(files):
                low = f.lower()
                if not low.endswith(exts):
                    continue
                p = os.path.join(root, f)
                try:
                    if low.endswith(".json"):
                        with open(p, "r", encoding="utf-8") as fh:
                            entries += _flatten(json.load(fh))
                    else:
                        txt = Path(p).read_text(encoding="utf-8", errors="ignore")
                        for i, chunk in enumerate(_chunk_text(txt)):
                            entries.append({"id": f"{p}#{i}", "type": "doc",
                                            "name": f, "text": chunk})
                except Exception:  # noqa: BLE001
                    continue
        return cls(entries)

    def _build_index(self) -> None:
        self._doc_tokens = []
        self._df = {}
        self._by_type = {}
        for e in self.entries:
            toks = _char_bigrams(e.get("text", ""))
            self._doc_tokens.append(toks)
            for t in set(toks):
                self._df[t] = self._df.get(t, 0) + 1
            self._by_type.setdefault(e.get("type", ""), []).append(e)

    @property
    def loaded(self) -> bool:
        return bool(self.entries)

    @property
    def is_demo(self) -> bool:
        """知识库是否为占位脚手架（示例/演示数据）—— 此时不告警，避免误报。

        _flatten 用子键作 type（company 字段被打平为 name/legal_person…），
        故不依赖特定 type，而用「强脚手架标记 + 占位占比」判定：
        - 任一文本含 示例/演示/DEMO/样例 → 强信号直接判占位；
        - 或占位占比 ≥ 0.5 → 判占位。
        仅含个别"某"字（真实素材常见）不会误判。
        """
        if not self.entries:
            return False
        ph = sum(1 for e in self.entries if _is_placeholder(e.get("text", "")))
        if ph == 0:
            return False
        strong = any(("示例" in t or "演示" in t or "样例" in t
                      or "DEMO" in t.upper())
                     for t in (e.get("text", "") for e in self.entries))
        return strong or (ph / len(self.entries)) >= 0.5

    # ── 检索（BM25 over char bigrams）──────────────────────
    def retrieve(self, query: str, topk: int = 5) -> List[Dict[str, Any]]:
        if not self.entries:
            return []
        n = len(self.entries)
        avgdl = sum(len(t) for t in self._doc_tokens) / n if n else 1.0
        k1, b = 1.5, 0.75
        q_toks = _char_bigrams(query)
        scores = [0.0] * n
        for qt in q_toks:
            if qt not in self._df:
                continue
            idf = math.log((n - self._df[qt] + 0.5) / (self._df[qt] + 0.5) + 1.0)
            for i, dt in enumerate(self._doc_tokens):
                tf = dt.count(qt)
                if tf:
                    scores[i] += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len(dt) / avgdl))
        ranked = sorted(range(n), key=lambda i: scores[i], reverse=True)[:topk]
        return [dict(self.entries[i], score=round(scores[i], 3)) for i in ranked if scores[i] > 0]

    # ── 事实核查 ──────────────────────────────────────────
    def contains(self, value: str) -> bool:
        """value 是否出现在任一知识库条目文本中（归一化后子串）。"""
        v = _norm_text(value)
        if len(v) < 2:
            return True
        for e in self.entries:
            if v in _norm_text(e.get("text", "")):
                return True
        return False

    def _declared_texts(self, kind: str) -> List[str]:
        """返回该 claim 类别对应的「真实（非占位）」知识库条目归一化文本。"""
        t = _KIND_TO_TYPE.get(kind)
        if not t:
            return []
        out = []
        for e in self._by_type.get(t, []):
            txt = e.get("text", "")
            if not txt or _is_placeholder(txt):
                continue
            out.append(_norm_text(txt))
        return out

    def fact_check(self, text: str) -> List[Dict[str, str]]:
        """扫描正文中的「具体标识」并做声明式相对核查（D4 零幻觉重建）。

        判定原则（从绝对改为相对，消除占位 KB 误报）：
        1. KB 为空 → 无依据，不告警；
        2. KB 为占位脚手架（demo）→ 无法判定真实，不告警；
        3. 某类别 KB 未声明真实条目 → 无法判定，跳过；
        4. 仅当 KB 确有真实同类条目、且正文值不在其中 → 疑似编造/矛盾。
        """
        if not self.entries or self.is_demo:
            return []
        flagged: List[Dict[str, str]] = []
        for kind, pat in _CLAIM_PATTERNS.items():
            declared = self._declared_texts(kind)
            if not declared:
                continue  # KB 未声明该类别 → 无法判定，跳过
            for m in re.finditer(pat, text or ""):
                val = m.group(1).strip()
                if not val or _is_placeholder(val):
                    continue
                nv = _norm_text(val)
                if not any(nv in d for d in declared):
                    flagged.append({"kind": kind, "value": val,
                                    "note": "与知识库声明真实信息不符，疑似编造（零幻觉告警）"})
        return flagged


# ── 工具 ──────────────────────────────────────────────────
def _norm_text(t: str) -> str:
    return re.sub(r"[\s，。；;、：:,.!！?？()（）\[\]【】\"'\"'“”%‰]", "", t or "")


_PLACEHOLDERS = ("XX", "xx", "示例", "某", "待", "此处", "TODO", "xxx", "XXXX")


def _is_placeholder(val: str) -> bool:
    v = (val or "").strip()
    if not v:
        return True
    if any(p in v for p in _PLACEHOLDERS):
        return True
    # 全角/半角 X 串
    if set(v) <= set("Xx×"):
        return True
    return False


# 正文里可能暴露「编造具体信息」的模式（保守，仅捕获明显具体值）
_CLAIM_PATTERNS: Dict[str, str] = {
    "资质编号": r"(?:资质|证书|注册)[编证]?号[：:为]?\s*([A-Za-z0-9]{6,})",
    "项目经理": r"项目经理[：:为]?\s*([一-龥]{2,4}(?:工程师|建造师|经理)?)",
    "业绩项目": r"(?:类似业绩|已完成|承接)[：:为]?\s*([一-龥A-Za-z0-9（）()]{4,20}工程)",
    "人员证书号": r"(?:证书编号|注册号|执业证号)[：:为]?\s*([A-Za-z0-9]{5,})",
}


def extract_kb_for_generation(kb: "KnowledgeBase", query: str, topk: int = 8) -> str:
    """把检索到的知识库条目拼成可注入 LLM 提示的「真实素材块」（与 T2 联动）。

    占位脚手架（demo）不注入——避免把示例数据当真实素材喂给生成。
    """
    if not kb.loaded or kb.is_demo:
        return ""
    hits = kb.retrieve(query, topk=topk)
    if not hits:
        return ""
    lines = ["【真实企业素材（仅供引用，禁止超此编造）】"]
    for h in hits:
        lines.append(f"- （{h.get('type','')}）{h.get('text','')}")
    return "\n".join(lines)
