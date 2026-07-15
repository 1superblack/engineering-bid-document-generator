# -*- coding: utf-8 -*-
"""
LLM 扩写客户端 v7.2 — 自包含、零新依赖（仅标准库）

设计目标：
    为 RichChapter 富内容引擎提供可选的「大模型逐节扩写」能力，
    在模板正文之上二次生成专业、项目定制的标书段落，追平云端 SaaS 的正文质量。

关键约束：
    1. 仅使用标准库（urllib / ssl / json / re），不引入 requests 等第三方依赖，
       以保证 Skill 在 WorkBuddy 内可直接运行、发布包不膨胀。
    2. 默认关闭：未配置 BIDGEN_LLM_ENABLE 且未提供 llm_config.json 时不激活，
       行为与 v7.1 完全一致（纯模板）。
    3. 失败静默回退：任何网络/解析/超时异常都返回 None，由调用方回退模板，
       绝不抛异常中断标书生成。
    4. 兼容 OpenAI Chat Completions 协议（base_url 可指向任意 OpenAI 兼容网关，
       如 DeepSeek / Qwen / 通义 / 自建 vLLM 等）。

配置方式（二选一）：
    A. 环境变量：
        BIDGEN_LLM_ENABLE=1
        BIDGEN_LM_API_KEY=sk-xxx
        BIDGEN_LLM_BASE_URL=https://api.openai.com/v1   # 可选，默认该值
        BIDGEN_LLM_MODEL=gpt-4o-mini                   # 可选
    B. 配置文件 data/llm_config.json：
        {"enabled": true, "api_key": "sk-xxx", "base_url": "...", "model": "..."}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1200
DEFAULT_TIMEOUT = 60  # 秒


@dataclass
class LLMConfig:
    """LLM 连接配置。"""
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout: int = DEFAULT_TIMEOUT
    enabled: bool = True


def load_llm_config(config_path: Optional[str] = None) -> Optional["LLMClient"]:
    """读取 LLM 配置并构造客户端。

    返回 None 表示未启用（默认行为），调用方应回退到模板生成。
    优先级：环境变量 > 配置文件 > 默认值。
    """
    env_enable = os.environ.get("BIDGEN_LLM_ENABLE", "").strip().lower() \
        in ("1", "true", "yes", "on")
    env_key = os.environ.get("BIDGEN_LLM_API_KEY", "").strip()
    env_base = os.environ.get("BIDGEN_LLM_BASE_URL", "").strip()
    env_model = os.environ.get("BIDGEN_LLM_MODEL", "").strip()

    file_cfg: Dict[str, Any] = {}
    candidates = [config_path] if config_path else [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "llm_config.json"),
    ]
    for p in candidates:
        try:
            if p and os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    file_cfg = json.load(f) or {}
                break
        except Exception:
            pass

    file_enable = bool(file_cfg.get("enabled"))
    file_key = (file_cfg.get("api_key") or "").strip()
    file_base = (file_cfg.get("base_url") or "").strip()
    file_model = (file_cfg.get("model") or "").strip()

    is_enabled = env_enable or file_enable
    api_key = env_key or file_key
    if not is_enabled or not api_key:
        return None

    cfg = LLMConfig(
        api_key=api_key,
        base_url=env_base or file_base or DEFAULT_BASE_URL,
        model=env_model or file_model or DEFAULT_MODEL,
        temperature=float(file_cfg.get("temperature", DEFAULT_TEMPERATURE)),
        max_tokens=int(file_cfg.get("max_tokens", DEFAULT_MAX_TOKENS)),
        timeout=int(file_cfg.get("timeout", DEFAULT_TIMEOUT)),
        enabled=True,
    )
    return LLMClient(cfg)


class LLMClient:
    """OpenAI 兼容的 Chat Completions 客户端（标准库实现）。"""

    def __init__(self, config: LLMConfig,
                 transport: Optional[Callable[[str, str], Optional[str]]] = None):
        self.config = config
        self._cache: Dict[str, Optional[str]] = {}
        # transport 可注入，便于测试（mock 真实 HTTP）
        self._transport = transport or self._http_chat

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled)

    # ── 公共入口 ──────────────────────────────────────────────
    def expand_section(self, section_title: str, bullet_points: List[str],
                       project_ctx: Dict[str, Any],
                       parse_result: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """对单个章节内容块进行大模型扩写。

        Args:
            section_title: 内容块标题（如"施工进度计划"）
            bullet_points: 该块的要点列表（来自评分策略 must_have/bonus 等）
            project_ctx: 项目上下文（含公司/项目经理/工期等）
            parse_result: 招标文件解析结果（注入评分项/红线等）

        Returns:
            扩写后的纯文本（多段落，用空行分隔）；失败/未启用返回 None。
        """
        if not self.enabled:
            return None
        cache_key = self._cache_key(section_title, bullet_points, project_ctx)
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = self._build_prompt(section_title, bullet_points, project_ctx, parse_result)
        try:
            raw = self._transport(self._system_prompt(), prompt)
        except Exception:
            raw = None
        result = self._clean(raw) if raw else None
        self._cache[cache_key] = result
        return result

    # ── 提示词 ───────────────────────────────────────────────
    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是一名资深投标书编写专家，擅长编写中国工程招投标技术标/商务标的正文。"
            "请用专业、严谨、符合行业规范的书面语扩写内容。"
            "要求：1) 紧扣所给要点，不遗漏；2) 结合项目与企业信息，避免空话套话；"
            "3) 体现对评分项与废标红线的响应；4) 只输出正文段落，不要标题、不要编号、"
            "不要 Markdown 标题符号，段落之间用空行分隔；5) 语言通顺、可直接用于标书。"
        )

    def _build_prompt(self, section_title, bullet_points, project_ctx, parse_result) -> str:
        ctx = project_ctx or {}
        lines = [f"请编写标书章节「{section_title}」的详细正文。", ""]
        lines.append("=== 项目信息 ===")
        if ctx.get("proj_brief"):
            lines.append(f"项目概况：{ctx['proj_brief']}")
        if ctx.get("company_name"):
            lines.append(f"投标单位：{ctx['company_name']}")
        if ctx.get("pm_name"):
            lines.append(f"项目经理：{ctx.get('pm_name')}（{ctx.get('pm_cert') or '相应执业资格'}）")
        if ctx.get("duration"):
            lines.append(f"工期：{ctx['duration']}")
        if ctx.get("divisions"):
            lines.append(f"分项工程：{'、'.join(ctx['divisions'][:4])}")
        if ctx.get("quals_top"):
            lines.append(f"企业资质：{ctx['quals_top']}")
        if ctx.get("similar_top"):
            lines.append(f"类似业绩：{ctx['similar_top']}")
        lines.append("")
        lines.append("=== 必须涵盖的要点 ===")
        for bp in (bullet_points or []):
            if bp:
                lines.append(f"- {bp}")
        # 注入评分项/红线
        pr = parse_result or {}
        score_items = pr.get("score_items") or []
        if score_items:
            lines.append("")
            lines.append("=== 评分项（须逐条响应） ===")
            for it in score_items[:12]:
                name = it.get("name") or it.get("title") or ""
                score = it.get("score") or it.get("weight") or ""
                if name:
                    lines.append(f"- {name}（{score}分）")
        red = pr.get("red_line_clauses") or []
        disq = pr.get("disqualify_clauses") or []
        clauses = [c.get("content") if isinstance(c, dict) else c for c in (red + disq)]
        clauses = [c for c in clauses if c][:10]
        if clauses:
            lines.append("")
            lines.append("=== 废标/红线条款（须避免触发） ===")
            for c in clauses:
                lines.append(f"- {c}")
        lines.append("")
        lines.append("请直接输出正文段落（2~4 段，段落间空行）。")
        return "\n".join(lines)

    # ── HTTP（标准库） ───────────────────────────────────────
    def _http_chat(self, system: str, user: str) -> Optional[str]:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.config.api_key}")
        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=self.config.timeout, context=ctx) as resp:
                body = resp.read().decode("utf-8")
            obj = json.loads(body)
            return obj["choices"][0]["message"]["content"]
        except Exception:
            return None

    # ── 工具 ─────────────────────────────────────────────────
    @staticmethod
    def _clean(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        t = text.strip()
        # 去掉 ``` 代码围栏
        if t.startswith("```"):
            t = t.split("\n", 1)[-1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[:-3]
        t = t.strip()
        # 去掉行首 Markdown 标题符号与加粗符号，保留纯文本
        t = re.sub(r'(?m)^#{1,6}\s*', '', t)
        t = t.replace("**", "")
        return t or None

    @staticmethod
    def _cache_key(section_title, bullet_points, project_ctx) -> str:
        h = hashlib.md5()
        h.update((section_title or "").encode("utf-8"))
        h.update(json.dumps(bullet_points or [], ensure_ascii=False).encode("utf-8"))
        h.update(json.dumps(project_ctx or {}, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        return h.hexdigest()
