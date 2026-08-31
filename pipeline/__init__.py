# -*- coding: utf-8 -*-
"""Pipeline 编排核心（ADR-001 实现）。

把 main.generate_bid_document 的 8+ 内联环节拆成可独立注册、独立测试、
失败可隔离的 Stage。

设计约束（来自架构设计书 v4）：
- 仅新增代码，不修改 main.py / 各业务模块本身 → 可逆、低风险。
- Stage 内部「延迟导入」业务函数，包本身仅依赖标准库，可单独 import。
- StageContext 为贯穿各阶段的可序列化上下文对象（满足 ADR-003 异步缝预备）。
- 企业画像相关能力按 ADR-005 已删除，不在本管线中登记。
"""
from .context import StageContext, StageOutcome, StageStatus
from .stage import Stage
from .orchestrator import PipelineOrchestrator
from .registry import (
    STAGE_REGISTRY,
    register_stage,
    build_default_pipeline,
)

__all__ = [
    "StageContext",
    "StageOutcome",
    "StageStatus",
    "Stage",
    "PipelineOrchestrator",
    "STAGE_REGISTRY",
    "register_stage",
    "build_default_pipeline",
]
