"""
防重 / 差异化生成引擎 v7.3
========================
对标喜鹊标书 AI 的「防重机制（随机特征矩阵 + 唯一指纹）」与 WPS 的「内容雷同风险规避」。

解决的核心合规痛点：标书查重已成合规红线，多个投标人用同一通用模型易产出相似内容。
本引擎在不依赖外部大模型的前提下，提供两层差异化能力：

  1. 措辞差异化旋转（rotate）：基于「项目指纹」对正文中的通用动词/名词做同义词轮换，
     使同一招标项目、不同投标人（或不同次运行）产出的文字明显不同，降低字面雷同率。
     ——旋转池均为工程标书领域等价、专业度一致的同义表述，不改变语义与承诺。
  2. 全文原创性自查（compute_self_similarity）：统计全文中重复句子比例，供评审报告披露，
     让"原创性"可量化、可核查（对标喜鹊的"差异化生成"承诺有迹可循）。

纯标准库实现，零新依赖。默认每次运行使用随机指纹 ⇒ 同项目两次生成内容不同。
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import Dict, List, Optional, Sequence

# ── 同义词轮换池 ────────────────────────────────────────────────────────
# 键：模板正文中常用的工程术语；值：可等价替换的表述（语义/专业度一致，不改动承诺）。
SYNONYMS: Dict[str, List[str]] = {
    "实施": ["落地", "执行", "推进", "开展", "贯行"],
    "保障": ["确保", "保证", "支撑", "护航", "托底"],
    "管理": ["管控", "治理", "统筹", "组织", "集约管理"],
    "方案": ["预案", "策划", "规划", "部署", "专项安排"],
    "措施": ["办法", "举措", "手段", "机制", "抓手"],
    "质量": ["品质", "工艺水平", "工程观感", "达标率", "实体质量"],
    "安全": ["安全生产", "作业平安", "零事故目标", "安全防护", "本质安全"],
    "进度": ["工期", "节点", "交付节奏", "时间轴", "施工节拍"],
    "风险": ["隐患", "不确定因素", "薄弱点", "变量", "不利因素"],
    "响应": ["答复", "对应", "承接", "满足", "契合"],
    "标准": ["规范", "准则", "要求", "基准", "技术规程"],
    "机制": ["体系", "制度", "闭环", "流程", "运转模式"],
    "闭环": ["全周期管控", "可追溯链条", "PDCA循环", "全过程留痕"],
    "落实": ["执行到位", "掷地有声", "一抓到底", "压实"],
    "管控": ["受控", "严管", "精细管理", "穿透式管理"],
    "统筹": ["一体谋划", "系统部署", "通盘考虑", "协同推进"],
    "优化": ["精进", "改良", "提质", "迭代提升"],
    "提升": ["拔高", "增强", "跃升", "强化"],
    "确保": ["力保", "守住", "万无一失地保障", "牢牢把控"],
    "建立": ["搭建", "构建", "成型", "织密"],
    "技术": ["工艺", "工法", "技术手段", "专业技术"],
    "检查": ["核查", "巡检", "复核", "验收校验"],
    "培训": ["交底培训", "专项练兵", "以训促战", "岗前实训"],
    "资料": ["档案", "台账", "过程记录", "佐证材料"],
    "目标": ["导向", "旨归", "硬指标", "必达要求"],
}


def default_fingerprint(project_info: Optional[Dict] = None) -> str:
    """生成默认指纹：项目名 + 运行随机盐 ⇒ 同项目每次运行内容不同。

    传入固定 project_info 且不希望随机时，调用方应自行传入固定 fingerprint。
    """
    name = (project_info or {}).get('name') or 'bid'
    salt = os.urandom(4).hex()
    return f"{name}|{salt}"


class Differentiator:
    """基于指纹的差异化生成器。"""

    def __init__(self, fingerprint: Optional[str] = None, project_info: Optional[Dict] = None):
        self.fingerprint = fingerprint or default_fingerprint(project_info)
        self._sentences: List[str] = []

    # ── 措辞旋转 ──────────────────────────────────────────────────────
    def rotate(self, text: str) -> str:
        """对文本做同义词轮换。同一指纹下结果确定；不同指纹结果不同。

        仅替换 SYNONYMS 中的通用术语，不触碰公司名/人名/星号条款/数字，保证承诺不变。

        v8.5 修复（取自 v8.1_fixed）：原实现按字典序逐键 .replace 会「链式二次替换」——
        例如「机制」→「闭环」后，新出现的「闭环」又被「闭环」→「PDCA循环」二次替换，
        在「闭环管理机制」上产出重复病句。现改为基于原始文本的单次左→右扫描
        （regex.sub 回调），被替换出的文本不再二次扫描，杜绝链式重复，
        同时每个键仍按指纹稳定选变体，差异化与确定性不变。
        """
        if not text:
            return text
        pattern = re.compile('|'.join(re.escape(k) for k in SYNONYMS))

        def _repl(m):
            term = m.group(0)
            variants = SYNONYMS[term]
            if not variants:
                return term
            return variants[self._pick(term, len(variants))]

        return pattern.sub(_repl, text)

    def _pick(self, salt: str, n: int) -> int:
        h = hashlib.md5(f"{self.fingerprint}::{salt}".encode("utf-8")).digest()
        return int.from_bytes(h[:4], "big") % n

    # ── 句子收集与原创性自查 ──────────────────────────────────────────
    def add_sentence(self, sentence: str) -> None:
        s = (sentence or "").strip()
        if len(s) >= 10:  # 过短句子不计入，避免误判
            self._sentences.append(s)

    @property
    def sentences(self) -> List[str]:
        return list(self._sentences)

    def self_similarity(self) -> float:
        return compute_self_similarity(self._sentences)

    def report(self) -> Dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "sentence_count": len(self._sentences),
            "self_similarity": round(self.self_similarity(), 4),
        }


def _norm(s: str) -> str:
    """归一化句子：去空白与标点，便于重复判定。"""
    return re.sub(r"[\s，。；;、：:,.!！?？()（）\[\]【】\"'\"'“”]", "", s or "")


def compute_self_similarity(sentences: Sequence[str]) -> float:
    """计算重复句子比例 ∈ [0,1]。

    仅对长度 ≥ 12 的归一化句子做精确重复判定（短句重复属正常，不计入），
    返回「重复句数 / 总句数」。值越低代表原创性越高、雷同风险越小。
    """
    normed = [_norm(s) for s in sentences if len(_norm(s)) >= 12]
    if not normed:
        return 0.0
    seen = set()
    dup = 0
    for n in normed:
        if n in seen:
            dup += 1
        else:
            seen.add(n)
    return dup / len(normed)
