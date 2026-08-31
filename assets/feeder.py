# -*- coding: utf-8 -*-
"""AssetFeeder：资产与知识支撑层的统一加载与注入。

背景（架构设计书 v4 · 修订A）：
原引擎把「规范库 / 模板 / 同义词」当作各处隐式 import 的散落文件，
导致资产与业务逻辑耦合、难以扩展（如新增行业模板要改代码）。
本支撑层把它们提升为独立的「资产上下文」：

- 通过「约定文件名」发现，不硬编码业务路径；
- 按类型分派加载：.json→dict，.md→text，.py→module 命名空间；
- feed(ctx) 把资产推入 StageContext.store['assets'][<kind>]，供生成等 Stage 消费；
- 加载失败仅告警、不阻断（延续「失败不阻断生成」语义）；
- 整个包只依赖标准库，可在无引擎环境 import / 测试。

注意：本层只做「资产的发现—加载—注入」这一薄缝，不实现任何生成逻辑；
是否启用、用哪些资产由执行管线（或入口函数）决定，保持依赖方向单向
（执行上下文 → 支撑层，逆之不成立）。
"""
from __future__ import annotations

import importlib.util
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)

# 资产种类 → 约定文件名
DEFAULT_FILES: Dict[str, str] = {
    "standards_db": "standards_db.py",   # 国标/行标/检查清单/职责库（.py 数据模块）
    "synonyms": "synonyms.json",         # 同义词归一化词典（.json）
    "templates": "templates.md",         # 章节模板（.md）
    "chapter_templates": "chapter_templates.md",  # 分章模板（.md）
    "waste_bid_keywords": "waste_bid_keywords.json",  # 废标/实质性条款高频关键词（.json）
    "platform_formats": "platform_formats.json",  # 电子招投标平台专用加密格式知识（.json）
    "schedule_phases": "schedule_phases.json",  # 施工进度横道图阶段与比例（.json）
}

DEFAULT_KINDS = frozenset(DEFAULT_FILES.keys())

# 注入到 ctx.store 时的顶层键
ASSETS_KEY = "assets"


@dataclass(frozen=True)
class AssetKind:
    """单个资产种类的描述（便于扩展时登记新种类）。"""

    name: str
    filename: str
    loader: str  # "json" | "text" | "module"

    @property
    def store_key(self) -> str:
        return f"{ASSETS_KEY}.{self.name}"


# 默认登记表
_KIND_REGISTRY: Dict[str, AssetKind] = {
    "standards_db": AssetKind("standards_db", "standards_db.py", "module"),
    "synonyms": AssetKind("synonyms", "synonyms.json", "json"),
    "templates": AssetKind("templates", "templates.md", "text"),
    "chapter_templates": AssetKind("chapter_templates", "chapter_templates.md", "text"),
    "waste_bid_keywords": AssetKind("waste_bid_keywords", "waste_bid_keywords.json", "json"),
    "platform_formats": AssetKind("platform_formats", "platform_formats.json", "json"),
    "schedule_phases": AssetKind("schedule_phases", "schedule_phases.json", "json"),
}


class AssetFeeder:
    """资产发现 / 加载 / 注入器。

    典型用法::

        feeder = AssetFeeder(base_dir="/path/to/engine")
        feeder.feed(ctx)   # 把发现的资产推入 ctx.store['assets']

    或按需取用::

        db = feeder.load("standards_db")   # 返回 module 或 None
        syns = feeder.load("synonyms")      # 返回 dict 或 None
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        enabled: Optional[Any] = None,
        kinds: Optional[Dict[str, AssetKind]] = None,
    ) -> None:
        self.base_dir: Optional[Path] = Path(base_dir) if base_dir else None
        self.enabled = frozenset(enabled) if enabled is not None else DEFAULT_KINDS
        self._kinds = kinds or _KIND_REGISTRY
        self._cache: Dict[str, Any] = {}

    # -- 发现 ----------------------------------------------------------------
    def discover(self) -> Dict[str, Path]:
        """返回已发现（文件存在）的资产种类 → 路径。"""
        found: Dict[str, Path] = {}
        if self.base_dir is None:
            return found
        for kind in self.enabled:
            spec = self._kinds.get(kind)
            if spec is None:
                continue
            p = self.base_dir / spec.filename
            if p.is_file():
                found[kind] = p
        return found

    # -- 加载 ----------------------------------------------------------------
    def load(self, kind: str) -> Any:
        """加载某一类资产（带缓存）。文件缺失或解析失败返回 None。"""
        if kind in self._cache:
            return self._cache[kind]
        spec = self._kinds.get(kind)
        if spec is None or self.base_dir is None:
            self._cache[kind] = None
            return None
        path = self.base_dir / spec.filename
        if not path.is_file():
            _log.warning("资产缺失，跳过: %s (%s)", kind, path)
            self._cache[kind] = None
            return None
        try:
            if spec.loader == "json":
                value = self._load_json(path)
            elif spec.loader == "text":
                value = self._load_text(path)
            elif spec.loader == "module":
                value = self._load_module(path)
            else:
                raise ValueError(f"未知加载器: {spec.loader}")
            self._cache[kind] = value
            return value
        except Exception as exc:  # noqa: BLE001 - 支撑层失败不应阻断主流程
            _log.warning("资产加载失败（不阻断）: %s | %s: %s", kind, type(exc).__name__, exc)
            self._cache[kind] = None
            return None

    def load_all(self) -> Dict[str, Any]:
        """加载所有启用且已发现的资产。"""
        return {kind: self.load(kind) for kind in self.discover()}

    # -- 注入 ----------------------------------------------------------------
    def feed(self, ctx: Any) -> Dict[str, str]:
        """把已发现资产推入 ctx.store['assets']。

        返回 {kind: store_key} 的成功注入映射，便于调用方记录。
        """
        store = getattr(ctx, "store", None)
        if store is None:
            _log.warning("ctx 无 store 属性，跳过资产注入")
            return {}
        assets = store.setdefault(ASSETS_KEY, {})
        injected: Dict[str, str] = {}
        for kind, path in self.discover().items():
            value = self.load(kind)
            if value is None:
                continue
            assets[kind] = value
            injected[kind] = f"{ASSETS_KEY}.{kind}"
        return injected

    # -- 信息 ----------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        """供日志 / 运维面板使用。"""
        discovered = self.discover()
        return {
            "base_dir": str(self.base_dir) if self.base_dir else None,
            "enabled": sorted(self.enabled),
            "discovered": {k: str(v) for k, v in discovered.items()},
            "loaded": [k for k in discovered if self._cache.get(k) is not None],
        }

    # -- 具体加载器 ----------------------------------------------------------
    @staticmethod
    def _load_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def _load_text(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _load_module(path: Path) -> Any:
        """按文件路径加载为独立 module 命名空间（不污染 sys.modules）。"""
        mod_name = f"_asset_{abs(hash(str(path)))}"
        spec = importlib.util.spec_from_file_location(mod_name, str(path))
        if spec is None or spec.loader is None:
            raise ImportError(f"无法为资产创建模块规范: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
