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
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# 双后端：local = 本机 vLLM/Ollama（数据不出本机）；cloud = 云端 API（出网前脱敏）
DEFAULT_LOCAL_BASE_URL = "http://localhost:8000/v1"
DEFAULT_CLOUD_BASE_URL = "https://api.openai.com/v1"
DEFAULT_BASE_URL = DEFAULT_CLOUD_BASE_URL
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1200
DEFAULT_TIMEOUT = 60  # 秒

# 生成结果中的占位桩/思维链泄漏标记：命中即丢弃该段落
_STUB_META_TOKENS = ("待补充", "TODO", "写作要求", "注意不能出现", "这里“")


@dataclass
class LLMConfig:
    """LLM 连接配置。

    backend: "local" 默认，指向本机网关（数据不出本机）；
             "cloud" 指向云端兼容网关，出网前自动实体脱敏（需 Masker）。
    mask: 是否启用出网脱敏。本地后端默认关闭（数据本就不出网），
         云端后端默认开启（隐私红线）。
    """
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout: int = DEFAULT_TIMEOUT
    enabled: bool = True
    backend: str = "local"
    mask: bool = False
    rpm: int = 0                 # 每分钟最大请求数；0 = 不限速（仅建议本地）
    thinking: bool = False       # DeepSeek V4 双模式：False=非思考（正文生成用，快/便宜）
    max_retries: int = 4         # 429 限流退避重试次数
    kb_path: Optional[str] = None  # 企业知识库 JSON 路径（RAG 注入正文）


def _codex_env_llm():
    """读取当前 Codex 环境实际启用的 LLM 凭据（~/.codex/config.toml）。

    跟随 Codex CLI 的 model_provider 配置（不限 deepseek），取对应 provider 的
    base_url 与 api_key / experimental_bearer_token；与 Codex CLI 同一把钥匙，
    skill 无需单独配置密钥。本客户端走 OpenAI Chat Completions 兼容端点。
    返回 (api_key, base_url, model)；读取失败返回 (None, None, None)。
    """
    try:
        import tomllib
    except Exception:
        return None, None, None
    try:
        from pathlib import Path

        codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        cfg_path = codex_home / "config.toml"
        if not cfg_path.is_file():
            return None, None, None
        cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
        provider = cfg.get("model_provider") or "deepseek"
        mp = (cfg.get("model_providers") or {}).get(provider) or {}
        key = ((mp.get("experimental_bearer_token") or mp.get("api_key")) or "").strip()
        base = (mp.get("base_url") or "").strip().rstrip("/")
        model = (cfg.get("model") or "").strip()
        if key and base:
            return key, base, model
    except Exception:
        pass
    return None, None, None


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
    env_backend = os.environ.get("BIDGEN_LLM_BACKEND", "").strip().lower()
    # 当前 Codex 环境 LLM：与 Codex CLI 同源（~/.codex/config.toml → model_providers.deepseek）
    codex_key, codex_base, codex_model = _codex_env_llm()
    # 通用平台环境变量兜底（WorkBuddy / OpenAI 系平台常注入 OPENAI_*；兼容 DeepSeek/Qwen/GLM 等）
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    openai_base = os.environ.get("OPENAI_BASE_URL", os.environ.get("OPENAI_API_BASE", "")).strip().rstrip("/")
    openai_model = os.environ.get("OPENAI_MODEL", "").strip()

    file_cfg: Dict[str, Any] = {}
    candidates = [config_path] if config_path else [
        # 兼容两种布局：llm_client.py 直接在 skill 根目录（flat），或位于 bid_core/ 子目录
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "llm_config.json"),
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
    file_backend = str(file_cfg.get("backend", "")).strip().lower()
    file_rpm = int(file_cfg.get("rpm", 0) or 0)
    file_thinking = bool(file_cfg.get("thinking", False))
    file_retries = int(file_cfg.get("max_retries", 4) or 4)
    file_kb = (file_cfg.get("kb_path") or "").strip()

    is_enabled = env_enable or file_enable
    api_key = env_key or file_key or codex_key or openai_key
    if not is_enabled or not api_key:
        return None

    # 后端：环境变量 > 配置文件 > Codex 环境凭据 > 通用 OPENAI_* > 默认 local
    backend = env_backend or file_backend or ("cloud" if (codex_key or openai_key) else "local")
    if backend not in ("local", "cloud"):
        backend = "local"

    # base_url：未显式给定时按后端取默认（local→本机 vLLM，cloud→云端网关）
    if env_base or file_base or codex_base or openai_base:
        base_url = env_base or file_base or codex_base or openai_base
    else:
        base_url = DEFAULT_LOCAL_BASE_URL if backend == "local" else DEFAULT_CLOUD_BASE_URL

    # 脱敏开关：云端后端默认开启（隐私红线）；本地后端默认关闭（不出网）
    env_mask = os.environ.get("BIDGEN_LLM_MASK", "").strip().lower()
    mask = (env_mask in ("1", "true", "yes", "on")) if env_mask else (backend == "cloud")

    # 知识库默认路径：data/user_knowledge_base.json（与 Skill 约定一致）
    skill_data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    kb_path = file_kb or os.path.join(skill_data, "user_knowledge_base.json")

    cfg = LLMConfig(
        api_key=api_key,
        base_url=base_url,
        model=env_model or file_model or codex_model or openai_model or DEFAULT_MODEL,
        temperature=float(file_cfg.get("temperature", DEFAULT_TEMPERATURE)),
        max_tokens=int(file_cfg.get("max_tokens", DEFAULT_MAX_TOKENS)),
        timeout=int(file_cfg.get("timeout", DEFAULT_TIMEOUT)),
        enabled=True,
        backend=backend,
        mask=mask,
        rpm=file_rpm,
        thinking=file_thinking,
        max_retries=file_retries,
        kb_path=kb_path,
    )
    return LLMClient(cfg)


def write_llm_config(backend: str = "local", api_key: Optional[str] = None,
                     base_url: Optional[str] = None, model: Optional[str] = None,
                     config_path: Optional[str] = None) -> str:
    """持久化 LLM 偏好（两选项 UX 的落盘点）。

    本地优先：backend 默认 "local"，base_url 默认指向本机 vLLM，mask 默认关闭；
    选 "cloud" 时 mask 默认开启（出网脱敏）。其它字段（api_key/model）与已有配置合并，
    不覆盖用户已填值（除非显式传入）。

    Returns: 配置文件绝对路径。
    """
    backend = "cloud" if str(backend).strip().lower() == "cloud" else "local"
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "llm_config.json")

    existing: Dict[str, Any] = {}
    try:
        if os.path.isfile(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                existing = json.load(f) or {}
    except Exception:
        existing = {}

    existing["backend"] = backend
    existing["enabled"] = True
    if api_key:
        existing["api_key"] = api_key
    if model:
        existing["model"] = model
    if base_url:
        existing["base_url"] = base_url
    elif "base_url" not in existing or not existing.get("base_url"):
        existing["base_url"] = DEFAULT_LOCAL_BASE_URL if backend == "local" else DEFAULT_CLOUD_BASE_URL
    # 脱敏开关随后端联动：云端默认开，本地默认关（可被显式 api 字段覆盖）
    existing["mask"] = (backend == "cloud")

    try:
        os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"写入 LLM 配置失败: {config_path} | {e}")
    return os.path.abspath(config_path)


class LLMClient:
    """OpenAI 兼容的 Chat Completions 客户端（标准库实现）。

    脱敏（T2 双选项隐私方案）：当 config.backend=="cloud" 且已挂载 Masker 时，
    出网前对 prompt 做实体屏蔽、回传后对结果做本地还原 —— 云端看不到真实实体。
    本地后端（默认）数据不出本机，不脱敏（保留个性化质量）。
    """

    def __init__(self, config: LLMConfig,
                 transport: Optional[Callable[[str, str], Optional[str]]] = None,
                 masker: Optional[Any] = None):
        self.config = config
        self.masker = masker  # 可选 Masker（见 llm_mask.py）
        self._cache: Dict[str, Optional[str]] = {}
        # transport 可注入，便于测试（mock 真实 HTTP）
        self._transport = transport or self._http_chat
        self._last_call_ts: float = 0.0  # RPM 限速用，记录上次实际发请求时间
        self._kb_cache: Optional[List[str]] = None  # 知识库素材缓存

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled)

    def _should_mask(self) -> bool:
        """是否对本次出网内容做实体脱敏。"""
        return bool(self.config.mask) and self.config.backend == "cloud" \
            and self.masker is not None

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
        masked_prompt = self.masker.mask(prompt) if self._should_mask() else prompt
        try:
            raw = self._transport(self._system_prompt(), masked_prompt)
        except Exception:
            raw = None
        clean = self._clean(raw) if raw else None
        result = self.masker.unmask(clean) if (self._should_mask() and clean) else clean
        self._cache[cache_key] = result
        return result

    # ── 提示词 ───────────────────────────────────────────────
    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是一名资深投标书编写专家，擅长编写中国工程招投标技术标/商务标的正文。"
            "写作要求：1) 紧扣评分项与要点，逐条响应、不遗漏；"
            "2) 结合项目真实信息（工程类型/工期/规模/结构形式/企业资质业绩），"
            "落到具体措施与量化指标，杜绝空话套话；"
            "3) 专业书面语、句式规范、术语准确，符合施工组织设计文体；"
            "4) 每段 150~300 字，共 2~4 段；"
            "5) 只输出正文段落，不要标题、不要编号、不要 Markdown 符号，"
            "段落之间用空行分隔；6) 禁止编造资质、业绩、人名、证书编号或工程数据；"
            "不确定的具体数字（人员数量、金额、参数等）用「按招标文件及现场实际情况确定」"
            "表述，禁止使用「待补充」「TODO」等占位符。"
        )

    def chat(self, system: str, user: str) -> Optional[str]:
        """通用对话入口（供招标文件解析等结构化抽取场景）。

        失败或未启用返回 None，绝不抛异常。transport 可注入以便测试。
        云端后端 + 已挂载 Masker 时，对 user 做出入双向脱敏。
        """
        if not self.enabled:
            return None
        masked_user = self.masker.mask(user) if self._should_mask() else user
        try:
            raw = self._transport(system, masked_user)
        except Exception:  # noqa: BLE001
            return None
        return self.masker.unmask(raw) if (self._should_mask() and raw) else raw

    def _build_prompt(self, section_title, bullet_points, project_ctx, parse_result) -> str:
        ctx = project_ctx or {}
        # T2：从 user_context 解析真实实体做个性化（缺省时回退到顶层字段）
        uc = ctx.get("user_context")
        if not isinstance(uc, dict):
            uc = {}
        company = uc.get("company") or {}
        if not isinstance(company, dict):
            company = {}
        personnel = uc.get("key_personnel") or []
        if not isinstance(personnel, list):
            personnel = []
        pm_info = next((p for p in personnel
                        if isinstance(p, dict) and "经理" in (p.get("role", "") or "")), None)
        company_name = ctx.get("company_name") or (company.get("name") if isinstance(company, dict) else None)
        pm_name = ctx.get("pm_name") or (pm_info.get("name") if pm_info else None)
        pm_cert = ctx.get("pm_cert") or (pm_info.get("cert") if pm_info else None)

        lines = [f"请编写标书章节「{section_title}」的详细正文。", ""]
        lines.append("=== 项目信息 ===")
        if ctx.get("proj_brief"):
            lines.append(f"项目概况：{ctx['proj_brief']}")
        if company_name:
            lines.append(f"投标单位：{company_name}")
        if pm_name:
            lines.append(f"项目经理：{pm_name}（{pm_cert or '相应执业资格'}）")
        if ctx.get("area"):
            lines.append(f"建筑面积：{ctx['area']}㎡")
        if ctx.get("structure_type"):
            lines.append(f"结构/工程类型：{ctx['structure_type']}")
        if ctx.get("quality_target"):
            lines.append(f"质量目标：{ctx['quality_target']}")
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
        # 注入企业知识库真实素材（RAG）：让正文不再是空话，而是融入真实业绩/工艺/设备
        kb_items = self._load_kb()
        if kb_items:
            lines.append("=== 企业知识库真实素材（须自然融入正文，不得编造） ===")
            for it in kb_items:
                lines.append(f"- {it}")
            lines.append("")
        lines.append("=== 写作规范 ===")
        lines.append("- 紧扣上述评分项/要点逐条响应：重点章节充分展开，次要章节简洁")
        lines.append("- 引用项目真实信息，落到具体措施与量化指标，避免空话套话")
        lines.append("- 每段 150~300 字，全章节 2~4 段；专业书面语、术语准确")
        lines.append("- 禁止编造企业资质、业绩、人员姓名、证书编号或工程数据；"
                     "不确定的具体数字用「按招标文件及现场实际情况确定」表述，"
                     "禁止使用「待补充」「TODO」等占位符")
        lines.append("")
        lines.append("请直接输出正文段落（2~4 段，段落间空行，不要标题与编号）。")
        return "\n".join(lines)

    # ── 速率限制 ─────────────────────────────────────────────
    def _rate_gate(self) -> None:
        """RPM 限速：保证相邻请求间隔 ≥ 60/rpm 秒（仅当 rpm>0）。"""
        rpm = self.config.rpm
        if not rpm or rpm <= 0:
            return
        min_interval = 60.0 / rpm
        now = time.monotonic()
        wait = min_interval - (now - self._last_call_ts)
        if wait > 0:
            time.sleep(wait)
        self._last_call_ts = time.monotonic()

    # ── HTTP（标准库） ───────────────────────────────────────
    def _build_payload(self, system: str, user: str) -> Dict[str, Any]:
        """构造 OpenAI 兼容请求体（独立出来便于单测，如 non-thinking 标志）。"""
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        # 注意：DeepSeek V4 的 OpenAI 兼容接口不接受顶层 "thinking" 字段（会 400）。
        # 是否思考由 API 默认行为决定（默认开启 reasoning，但最终答案仍落在 content）；
        # 如需关闭思考以省 token，应使用各提供商的专有参数，不在本通用客户端内硬编码。
        return payload

    def _http_chat(self, system: str, user: str) -> Optional[str]:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        payload = self._build_payload(system, user)
        data = json.dumps(payload).encode("utf-8")
        for attempt in range(max(1, self.config.max_retries)):
            self._rate_gate()
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {self.config.api_key}")
            try:
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=self.config.timeout, context=ctx) as resp:
                    body = resp.read().decode("utf-8")
                obj = json.loads(body)
                msg = obj["choices"][0]["message"]
                # 只取 content；reasoning_content（思考链）绝不能写入标书正文
                content = msg.get("content") or ""
                return content or None
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    # 限流：指数退避后重试（不抛异常，遵守失败静默契约）
                    backoff = min(2 ** attempt, 30)
                    time.sleep(backoff)
                    continue
                return None
            except Exception:
                return None
        return None

    # ── 知识库（RAG 注入） ───────────────────────────────────
    def _load_kb(self) -> List[str]:
        """读取企业知识库 JSON，提取可融入正文的真实素材（业绩/工艺/设备/资质）。"""
        if self._kb_cache is not None:
            return self._kb_cache
        items: List[str] = []
        path = self.config.kb_path
        if not path or not os.path.isfile(path):
            self._kb_cache = items
            return items
        try:
            with open(path, "r", encoding="utf-8") as f:
                kb = json.load(f) or {}
            # 兼容多种结构：直接字符串列表、或含 achievements/projects/equipment 等键
            if isinstance(kb, list):
                items = [str(x) for x in kb if x]
            elif isinstance(kb, dict):
                for key in ("achievements", "projects", "similar_projects",
                            "equipment", "process", "technologies", "qualifications"):
                    val = kb.get(key)
                    if isinstance(val, list):
                        items.extend(str(x) for x in val if x)
                    elif val:
                        items.append(str(val))
                # 兜底：把任意短字符串值也收进来
                if not items:
                    for v in kb.values():
                        if isinstance(v, str) and len(v) < 200:
                            items.append(v)
        except Exception:
            items = []
        # 去重 + 截断，避免 prompt 爆炸
        seen = set()
        uniq = []
        for it in items:
            s = it.strip()
            if s and s not in seen:
                seen.add(s)
                uniq.append(s)
        self._kb_cache = uniq[:20]
        return self._kb_cache

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
        # 过滤含占位桩/写作要求的段落（防思维链泄漏）
        paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
        paras = [p for p in paras if not any(tok in p for tok in _STUB_META_TOKENS)]
        return "\n".join(paras) if paras else None

    @staticmethod
    def _cache_key(section_title, bullet_points, project_ctx) -> str:
        h = hashlib.md5()
        h.update((section_title or "").encode("utf-8"))
        h.update(json.dumps(bullet_points or [], ensure_ascii=False).encode("utf-8"))
        h.update(json.dumps(project_ctx or {}, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        return h.hexdigest()
