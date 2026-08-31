# -*- coding: utf-8 -*-
"""StageContext：贯穿所有 Stage 的上下文 / 产物对象。

设计点（对应 ADR-003 / ADR-004）：
- 所有阶段间传递的状态都集中在 ctx.store，不依赖全局变量、不互相 import 业务函数。
- ctx 可被序列化（to_dict 仅导出可 pickle 的内容），为将来「包进 Job Worker 做异步」预留缝。
- req / data / llm_client 在生成阶段基本只读；可写产物统一走 ctx.set(...)。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class StageStatus:
    """单个 Stage 的执行状态常量。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    BLOCKED = "blocked"  # 阻断性失败，导致管线中止


@dataclass
class StageOutcome:
    """单个 Stage 的执行结果记录（写入 ctx.meta['stages'] 供追踪）。"""

    name: str
    status: str = StageStatus.PENDING
    blocking: bool = False
    error: Optional[str] = None
    duration_ms: float = 0.0
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageContext:
    """一个请求从解析到交付的完整上下文。

    Attributes:
        req: 原始请求（BidRequest 或兼容对象）。生成阶段基本只读。
        data: request_to_dict(req) 后的扁平字典，兼容现有业务函数入参。
        llm_client: 可选的 LLM 扩写客户端（None 时业务回退模板）。
        store: 各 Stage 写入的中间产物（parse_result / feasibility_report /
              result_path / cross_doc_* / risk_library_findings / ...）。
        meta: 运行元信息（开始/结束时间、各 Stage 状态）。
    """

    req: Any = None
    data: Dict[str, Any] = field(default_factory=dict)
    llm_client: Optional[Any] = None
    store: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.store[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """供产物 / 异步序列化使用（ADR-003）。

        注意：req / llm_client 等可能不可序列化的对象不导出，只导出 data + store。
        """
        try:
            store_copy = copy.deepcopy(self.store)
        except Exception:
            store_copy = self.store
        return {
            "data": self.data,
            "store": store_copy,
            "meta": self.meta,
        }
