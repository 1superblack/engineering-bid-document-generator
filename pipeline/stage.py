# -*- coding: utf-8 -*-
"""Stage 抽象基类。

每个能力单元实现 run(ctx)；是否执行由 should_run(ctx) 决定；
run 抛异常时是否被阻断由 blocking 标记决定（见 PipelineOrchestrator）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .context import StageContext


class Stage(ABC):
    """管线中的一个能力单元。

    约定：
    - name: 唯一标识，用于注册表与追踪。
    - blocking: True 时，run 抛异常会中止整个管线；False 时仅记录失败并继续
      （保持与原 main.py「失败不阻断生成」语义一致）。
    - should_run(ctx): 是否执行（如按 enable_* 开关 / 前置产物是否存在）。
    - run(ctx): 执行业务逻辑，结果写入 ctx.store；可就地更新 ctx.req/data。
    """

    name: str = "stage"
    blocking: bool = False

    def should_run(self, ctx: StageContext) -> bool:  # noqa: D401
        """默认总是执行；子类按需覆盖（如按 enable_* 开关 / 前置产物）。"""
        return True

    @abstractmethod
    def run(self, ctx: StageContext) -> None:
        """执行逻辑。结果写入 ctx，不要求返回值。"""
        ...

    def __repr__(self) -> str:
        return f"<Stage {self.name!r} blocking={self.blocking}>"
