"""
以标写标 — 历史中标标书加载器 v1.0 — P1 升级（对标 WPS AI "参考范文/以标写标"）

加载一份历史中标标书（DOCX），提取：
    1. 章节结构大纲（标题层级 + 正文）
    2. 项目变量（公司名 / 法定代表人 / 项目经理 / 金额 / 工期 / 日期等）
    3. 写作风格样本（高频承诺句式、术语）

并基于新项目信息生成「变量替换映射」，便于在生成新标书时智能套用
参考标书的结构与措辞，实现"以标写标"。

设计原则:
    - 仅做结构与变量提取，不做内容抄袭（合规底线：仅复用结构/框架/风格）
    - 纯 python-docx 解析，不依赖 Word 应用
    - 任何解析异常均降级为空结构，不影响主流程
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from bid_core.logger import get_logger

log = get_logger(__name__)


class ReferenceLoader:
    """历史标书加载与变量提取。

    用法:
        ref = ReferenceLoader('path/to/winning_bid.docx').load()
        var_map = ref.build_variable_map(new_project_info)
        outline = ref.get_adapted_outline(new_project_info)
    """

    def __init__(self, path: str):
        self.path = path
        self.chapters: List[Dict[str, Any]] = []
        self.variables: Dict[str, str] = {}
        self.style_patterns: List[str] = []
        self.outline: List[str] = []
        self._raw_text: str = ''

    # ────────────────────────────────────────────────────────────
    # 主入口
    # ────────────────────────────────────────────────────────────
    def load(self) -> 'ReferenceLoader':
        """解析参考标书，填充 chapters / variables / style_patterns / outline。"""
        try:
            from docx import Document
            doc = Document(self.path)
        except Exception as exc:
            log.warning('参考标书加载失败(已降级为空结构): %s', exc, exc_info=True)
            return self

        paragraphs = doc.paragraphs
        self._raw_text = '\n'.join(p.text for p in paragraphs)

        self.chapters = self._extract_chapters(paragraphs)
        self.outline = [c['title'] for c in self.chapters if c['level'] == 1]
        self.variables = self._extract_variables(self._raw_text)
        self.style_patterns = self._extract_style_patterns(self._raw_text)
        log.info('参考标书解析完成: %d 个章节, %d 个变量, %d 条风格样本',
                 len(self.chapters), len(self.variables), len(self.style_patterns))
        return self

    # ────────────────────────────────────────────────────────────
    # 章节结构提取
    # ────────────────────────────────────────────────────────────
    def _extract_chapters(self, paragraphs) -> List[Dict[str, Any]]:
        chapters: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for p in paragraphs:
            text = (p.text or '').strip()
            if not text:
                continue
            level = self._heading_level(p)
            if level is not None:
                current = {
                    'title': text,
                    'level': level,
                    'text': '',
                    'word_count': 0,
                }
                chapters.append(current)
            elif current is not None:
                current['text'] += text + '\n'
                current['word_count'] += len(text)
        return chapters

    @staticmethod
    def _heading_level(p) -> Optional[int]:
        """根据段落样式推断标题层级。"""
        style_name = ''
        try:
            style_name = (p.style.name or '') if p.style else ''
        except Exception:
            pass
        if not style_name:
            return None
        if style_name.strip() == 'Title':
            return 0  # 文档标题单独归类，不计入章节大纲
        m = re.match(r'Heading\s*(\d+)', style_name, re.IGNORECASE)
        if m:
            return int(m.group(1))
        # 中文常见: 标题 1 / 一级标题
        m2 = re.match(r'标题\s*(\d+)', style_name)
        if m2:
            return int(m2.group(1))
        return None

    # ────────────────────────────────────────────────────────────
    # 变量提取
    # ────────────────────────────────────────────────────────────
    def _extract_variables(self, text: str) -> Dict[str, str]:
        vars_: Dict[str, str] = {}

        # 项目名称: 含"工程"且不含"投标文件/公司"的首个句子片段
        for cand in re.findall(r'([^\n，。；]{4,40}工程[^\n，。；]{0,20})', text):
            if '投标文件' not in cand and '公司' not in cand:
                vars_['project_name'] = cand.strip()
                break

        # 法定代表人
        m = re.search(r'法定代表人[：:]\s*([^\n，。；]{2,6})', text)
        if m:
            vars_['legal_person'] = m.group(1).strip()

        # 项目经理
        m = re.search(r'项目经理[：:]\s*([^\n，。；]{2,6})', text)
        if m:
            vars_['project_manager'] = m.group(1).strip()

        # 公司名（含 公司/集团/局/院 的最长高频词）
        org = self._find_org_name(text)
        if org:
            vars_['company'] = org

        # 金额（首个出现的万元/元数值）
        m = re.search(r'(\d[\d,]*\.?\d*)\s*(万?元|万元)', text)
        if m:
            vars_['amount'] = m.group(0).strip()

        # 工期（天数）
        m = re.search(r'工期[为是约]?\s*(\d+)\s*天', text)
        if m:
            vars_['duration_days'] = m.group(1)

        # 日期范围
        m = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)[^\n]{0,4}至(\d{4}年\d{1,2}月\d{1,2}日)', text)
        if m:
            vars_['date_range'] = f'{m.group(1)} 至 {m.group(2)}'

        return vars_

    @staticmethod
    def _find_org_name(text: str) -> Optional[str]:
        """从文本中识别最可能的投标单位名称。"""
        candidates = re.findall(r'([一-龥]{2,18}?(?:公司|集团|局|院|厂|中心))', text)
        if not candidates:
            return None
        # 取出现频率最高者
        freq: Dict[str, int] = {}
        for c in candidates:
            c = c.strip()
            if len(c) >= 4:
                freq[c] = freq.get(c, 0) + 1
        if not freq:
            return candidates[0]
        return max(freq.items(), key=lambda kv: kv[1])[0]

    # ────────────────────────────────────────────────────────────
    # 风格样本提取
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_style_patterns(text: str) -> List[str]:
        """提取高频"承诺/保证"类句式作为风格样本。"""
        patterns: List[str] = []
        # 承诺/保证/严格按照 等强承诺句式
        for m in re.finditer(r'([^\n。；]{4,40}?(?:承诺|保证|严格按照|依据|遵循|确保)[^\n。；]{0,30})', text):
            s = m.group(1).strip()
            if 8 <= len(s) <= 50:
                patterns.append(s)
        # 去重，最多保留 20 条
        seen = set()
        uniq = []
        for p in patterns:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
            if len(uniq) >= 20:
                break
        return uniq

    # ────────────────────────────────────────────────────────────
    # 变量替换映射 & 大纲适配
    # ────────────────────────────────────────────────────────────
    def build_variable_map(self, new_project_info: Dict[str, Any]) -> Dict[str, str]:
        """生成 参考标书变量 → 新项目变量 的替换映射。"""
        mapping: Dict[str, str] = {}
        # 公司名
        new_company = (new_project_info or {}).get('company', {})
        if isinstance(new_company, dict):
            new_company_name = new_company.get('name', '')
        else:
            new_company_name = str(new_company)
        if self.variables.get('company') and new_company_name:
            mapping[self.variables['company']] = new_company_name
        # 项目名称
        if self.variables.get('project_name') and new_project_info.get('name'):
            mapping[self.variables['project_name']] = new_project_info['name']
        # 法定代表人
        if self.variables.get('legal_person') and isinstance(new_company, dict):
            lp = new_company.get('legal_person', '')
            if lp:
                mapping[self.variables['legal_person']] = lp
        # 项目经理
        if self.variables.get('project_manager'):
            pm = self._extract_pm_from_context(new_project_info)
            if pm:
                mapping[self.variables['project_manager']] = pm
        return mapping

    @staticmethod
    def _extract_pm_from_context(pi: Dict[str, Any]) -> Optional[str]:
        uc = pi.get('user_context') or pi.get('company') or {}
        persons = uc.get('key_personnel', []) if isinstance(uc, dict) else []
        for p in persons:
            if isinstance(p, dict) and p.get('role') == '项目经理':
                return p.get('name', '')
        return None

    def get_adapted_outline(self, new_project_info: Dict[str, Any]) -> List[str]:
        """返回参考标书的一级章节大纲（用于新标书结构套用）。

        若参考标书无可用大纲，回退到新项目信息中的章节列表。
        """
        if self.outline:
            return self.outline
        chapters = (new_project_info or {}).get('chapters') or []
        if isinstance(chapters, list) and chapters:
            return [c if isinstance(c, str) else c.get('title', '') for c in chapters]
        return []

    def summary(self) -> Dict[str, Any]:
        """返回精简摘要（便于日志/调试）。"""
        return {
            'path': self.path,
            'chapter_count': len(self.chapters),
            'outline': self.outline,
            'variables': self.variables,
            'style_sample_count': len(self.style_patterns),
        }


def load_reference(path: str) -> ReferenceLoader:
    """模块级便捷入口。"""
    return ReferenceLoader(path).load()
