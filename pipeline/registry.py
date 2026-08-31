# -*- coding: utf-8 -*-
"""Stage 注册表 + 默认管线装配。

- STAGE_REGISTRY：name → Stage 类，供插件式扩展（如电子标书输出适配器）。
- register_stage：装饰器，类定义时自动登记。
- build_default_pipeline：按真实 Skill 源（v9.2.1，已移除 appendix_lockfill）的真实执行顺序装配默认管线。

注意：本模块在顶层不 import stages，避免循环依赖；
build_default_pipeline 内才延迟导入具体 Stage 类。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from .orchestrator import PipelineOrchestrator
from .stage import Stage

_log = logging.getLogger(__name__)

STAGE_REGISTRY: Dict[str, Type[Stage]] = {}


def register_stage(name: Optional[str] = None):
    """装饰器：将 Stage 类登记到 STAGE_REGISTRY（key 默认取类.name）。"""

    def _deco(cls: Type[Stage]) -> Type[Stage]:
        key = name or getattr(cls, "name", None) or cls.__name__
        STAGE_REGISTRY[key] = cls
        return cls

    return _deco


def build_default_pipeline() -> PipelineOrchestrator:
    """按默认顺序装配管线。

    顺序严格对齐原 main.generate_bid_document 的环节：
    解析 → 可行性 → 生成(核心,阻断) → 查重 → 废标风险库 → 评分闭环补强。
    """
    # 延迟导入，避免 registry 与 stages 的循环依赖
    from .stages import (
        TenderParseStage,
        FeasibilityStage,
        GenerationStage,
        DedupStage,
        RiskLibraryStage,
        ScoringReinforceStage,
    )

    stages: List[Stage] = [
        TenderParseStage(),
        FeasibilityStage(),
        GenerationStage(),
        DedupStage(),
        RiskLibraryStage(),
        ScoringReinforceStage(),
    ]
    _log.debug("装配默认管线: %s", [s.name for s in stages])
    return PipelineOrchestrator(stages=stages)
