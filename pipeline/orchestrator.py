# -*- coding: utf-8 -*-
"""PipelineOrchestrator：注册并按序 / 条件执行 Stage，标准化失败隔离。

与原 main.py 的语义对应：
- 原代码在每个环节用 `try/except` 内联「失败不阻断生成」；
- 本编排核心把该策略提升为一等公民：Stage.blocking 决定异常是否中止管线，
  非阻断 Stage 的异常被记录为 FAILED 并继续后续 Stage。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence

from .context import StageContext, StageOutcome, StageStatus
from .stage import Stage

_log = logging.getLogger(__name__)


class PipelineOrchestrator:
    """薄编排核心。

    - stages 可来自注册表（build_default_pipeline）或显式传入。
    - 执行模型：按列表顺序，逐 Stage 调用 should_run 决定是否执行；
      run 抛异常时：blocking=True → 记录 BLOCKED 并中止；blocking=False →
      记录 FAILED 并继续（保持与原 main.py「失败不阻断生成」语义一致）。
    - 返回最终 StageContext（含 meta['stages'] 各 Stage 状态），便于调用方拼装结果。
    """

    def __init__(self, stages: Optional[Sequence[Stage]] = None) -> None:
        self.stages: List[Stage] = list(stages or [])

    def register(self, stage: Stage) -> "PipelineOrchestrator":
        """追加一个 Stage（支持链式调用）。"""
        self.stages.append(stage)
        return self

    def run(self, ctx: StageContext) -> StageContext:
        """执行管线。返回携带各 Stage 状态的 ctx。"""
        ctx.meta.setdefault("stages", {})
        ctx.meta.setdefault("started_at", time.time())

        for stage in self.stages:
            outcome = StageOutcome(name=stage.name, blocking=stage.blocking)

            if not stage.should_run(ctx):
                outcome.status = StageStatus.SKIPPED
                ctx.meta["stages"][stage.name] = outcome.__dict__
                _log.debug("Stage 跳过: %s", stage.name)
                continue

            outcome.status = StageStatus.RUNNING
            _t0 = time.time()
            try:
                stage.run(ctx)
                outcome.status = StageStatus.SUCCESS
            except Exception as exc:  # noqa: BLE001 - 编排层统一兜底
                outcome.error = f"{type(exc).__name__}: {exc}"
                if stage.blocking:
                    outcome.status = StageStatus.BLOCKED
                    outcome.duration_ms = (time.time() - _t0) * 1000
                    ctx.meta["stages"][stage.name] = outcome.__dict__
                    _log.error("Stage 阻断性失败，管线中止: %s | %s", stage.name, outcome.error)
                    raise
                outcome.status = StageStatus.FAILED
                _log.warning("Stage 失败（不阻断）: %s | %s", stage.name, outcome.error)

            outcome.duration_ms = (time.time() - _t0) * 1000
            ctx.meta["stages"][stage.name] = outcome.__dict__
            if outcome.status == StageStatus.SUCCESS:
                _log.info("Stage 完成: %s (%.0fms)", stage.name, outcome.duration_ms)

        ctx.meta["finished_at"] = time.time()
        return ctx
