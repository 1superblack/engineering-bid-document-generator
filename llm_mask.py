# -*- coding: utf-8 -*-
"""T2 · 出网前实体脱敏 Masker（纯标准库，零新依赖）。

背景（用户决策「外置API + 脱敏 + 两选项」）：
技术标书虽不含报价等强隐私字段，但投标单位名称、项目经理姓名、执业证书号、
类似业绩名称仍属企业竞争情报。当用户选择「云端 API」后端时，这些真实实体
在出网前被替换为可逆占位符，回传后再本地还原 —— 实现「用云端提质，数据不出本机」。

设计约束：
- 仅标准库，零新依赖；
- 可逆：mask 记录 {占位符: 真值} 映射，unmask 还原；占位符不含任何真实信息；
- 精准：只屏蔽从 user_context / 知识库取到的「真实实体」，不碰通用词；
- 幂等友好：unmask 只替换已知占位符，无占位符则原样返回。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# 占位符样式：ASCII、无歧义、不会出现在正常标书正文里
def _token(i: int) -> str:
    return f"[[ENT_{i}]]"


class Masker:
    """可逆实体脱敏器。

    用法：
        m = Masker.from_user_context(req.user_context)
        masked_prompt = m.mask(prompt)        # 出网前
        raw = llm_call(masked_prompt)
        text = m.unmask(raw)                  # 回传后本地还原
    """

    def __init__(self) -> None:
        self._entities: List[str] = []          # 真实实体（长优先）
        self._token_to_real: Dict[str, str] = {}
        self._real_to_token: Dict[str, str] = {}
        self._counter = 0

    # ── 构造 ───────────────────────────────────────────────
    @classmethod
    def from_entities(cls, entities: List[str]) -> "Masker":
        m = cls()
        seen: set = set()
        cleaned: List[str] = []
        for e in entities:
            e = (e or "").strip()
            if not e or len(e) < 2 or e in seen:
                continue
            # 过滤明显占位/泛化词（这些不是真实实体，无需屏蔽）
            if e in ("XX", "xx", "某", "示例", "待补充", "TODO"):
                continue
            if set(e) <= set("Xx×"):
                continue
            seen.add(e)
            cleaned.append(e)
        # 长实体优先，避免短实体提前截断长实体的子串
        cleaned.sort(key=len, reverse=True)
        m._entities = cleaned
        return m

    @classmethod
    def from_user_context(cls, user_context: Optional[Dict[str, Any]]) -> "Masker":
        """从 user_context（嵌套结构）抽取真实实体。

        覆盖：投标单位名 / 法定代表人、项目经理及关键人员姓名、执业证书号、
        类似业绩名称、企业资质名称。
        """
        ents: List[str] = []
        uc = user_context or {}
        if not isinstance(uc, dict):
            return cls.from_entities(ents)

        company = uc.get("company") or {}
        if isinstance(company, dict):
            for key in ("name", "legal_person", "short_name"):
                v = company.get(key)
                if isinstance(v, str) and v.strip():
                    ents.append(v.strip())

        for person in (uc.get("key_personnel") or []):
            if not isinstance(person, dict):
                continue
            for key in ("name", "cert_no", "cert"):
                v = person.get(key)
                if isinstance(v, str) and v.strip():
                    ents.append(v.strip())

        for proj in (uc.get("similar_projects") or []):
            if isinstance(proj, dict):
                nm = proj.get("name")
                if isinstance(nm, str) and nm.strip():
                    ents.append(nm.strip())
            elif isinstance(proj, str) and proj.strip():
                ents.append(proj.strip())

        for qual in (uc.get("qualifications") or uc.get("qualification") or []):
            if isinstance(qual, dict):
                nm = qual.get("name")
                if isinstance(nm, str) and nm.strip():
                    ents.append(nm.strip())
            elif isinstance(qual, str) and qual.strip():
                ents.append(qual.strip())

        # 顶层也可能直接给出（向后兼容）
        for key in ("company_name", "pm_name", "pm_cert"):
            v = uc.get(key)
            if isinstance(v, str) and v.strip():
                ents.append(v.strip())

        return cls.from_entities(ents)

    @classmethod
    def from_kb(cls, kb: Any) -> "Masker":
        """从知识库抽取「真实（非占位）」实体（公司名/人员名/业绩名/证书号）。

        占位脚手架（demo）不抽取 —— 示例数据无需屏蔽。
        """
        ents: List[str] = []
        try:
            from knowledge_base import _is_placeholder  # noqa: PLC2701
        except Exception:  # noqa: BLE001
            def _is_placeholder(v):  # type: ignore
                return not v or "XX" in str(v) or "示例" in str(v)

        kb_entries = getattr(kb, "entries", None) or []
        for e in kb_entries:
            if not isinstance(e, dict):
                continue
            txt = e.get("text", "")
            nm = e.get("name")
            if nm and not _is_placeholder(str(nm)):
                ents.append(str(nm).strip())
            # 从文本里挑「工程」类业绩名与「证书/注册」类编号（保守）
            if txt and not _is_placeholder(txt):
                for tok in (txt.split("；") + txt.split(";")):
                    tok = tok.strip()
                    if ("工程" in tok or "项目" in tok) and len(tok) >= 4:
                        ents.append(tok)
                    if any(k in tok for k in ("证书编号", "注册号", "执业证号", "资质证书")):
                        ents.append(tok)
        return cls.from_entities(ents)

    # ── 屏蔽 / 还原 ───────────────────────────────────────
    def mask(self, text: str) -> str:
        """把真实实体替换为占位符，返回不含真实实体的文本。

        无实体或空文本则原样返回（零成本）。
        """
        if not text or not self._entities:
            return text
        out = text
        for ent in self._entities:
            if ent not in out:
                continue
            # 若该实体已被部分替换（理论上不会发生，因 token 不含真值），跳过
            if ent in self._real_to_token:
                token = self._real_to_token[ent]
            else:
                token = _token(self._counter)
                self._counter += 1
                self._token_to_real[token] = ent
                self._real_to_token[ent] = token
            out = out.replace(ent, token)
        return out

    def unmask(self, text: str) -> str:
        """把占位符还原为真实实体（回传后本地执行）。

        无占位符则原样返回。
        """
        if not text or not self._token_to_real:
            return text
        out = text
        for token, real in self._token_to_real.items():
            out = out.replace(token, real)
        return out

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def masked_count(self) -> int:
        return len(self._token_to_real)


def build_masker_from_request(req: Any) -> "Masker":
    """从请求对象抽取真实实体构造 Masker（兼容 BidRequest 与 dict 入参）。"""
    uc = getattr(req, "user_context", None)
    if uc is None and isinstance(req, dict):
        uc = req.get("user_context")
    if not isinstance(uc, dict):
        uc = {}
    return Masker.from_user_context(uc)
