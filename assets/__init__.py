# -*- coding: utf-8 -*-
"""资产与知识支撑层（修订A，独立 bounded context）。

把引擎里散落隐式 import 的资产（规范库 / 模板 / 同义词归一化）收敛为
一个可发现、可加载、可注入的统一支撑层。完全独立，不依赖引擎业务模块。
"""
from .feeder import AssetFeeder, AssetKind

__all__ = ["AssetFeeder", "AssetKind"]
