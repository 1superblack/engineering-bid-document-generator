"""v8.2: 包结构垫片 — 将扁平化模块映射为 bid_core / bid_technical 包路径

扁平化打包后，代码仍用 `from bid_core.xxx import` / `from bid_technical.xxx import`，
但根目录没有 bid_core/ / bid_technical/ 目录。

本模块注册一个 MetaPathFinder + Loader：
  - 当导入 `bid_core.formatter` / `bid_technical.generator` 等虚拟名时，
    加载根目录下同名的真实模块（如 formatter.py / generator.py），
    并将虚拟名在 sys.modules 中直接指向该真实模块对象（同一对象，非副本）。
  - 完全按需解析，不受导入顺序影响：彻底消除 v8.1 中 _load_order 顺序依赖导致的
    「generator 内部 `from bid_core.base_generator import` 时虚拟名尚未映射、
    从而 generator 静默加载失败、bid_technical.generator 永远无法导入」的问题。

正式部署环境（存在真实 bid_core/ bid_technical/ 目录）中本模块自动跳过。

用法：在 conftest.py 中 `import _package_shim` 即生效。
"""
import sys
import types
import importlib
import importlib.abc
import importlib.machinery
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 虚拟包路径 → 根目录真实模块名（同一对象映射；包名映射到对应包目录）
_MODULE_MAP = {
    # bid_core.xxx → 根目录 xxx
    'bid_core.logger': 'logger',
    'bid_core.user_context': 'user_context',
    'bid_core.formatter': 'formatter',
    'bid_core.reference_loader': 'reference_loader',
    'bid_core.ppt_generator': 'ppt_generator',
    'bid_core.hooks': 'hooks',
    'bid_core.ai_enhance': 'ai_enhance',
    'bid_core.data_loader': 'data_loader',
    'bid_core.dedup': 'dedup',
    'bid_core.base_generator': 'base_generator',
    'bid_core.deviation_checker': 'deviation_checker',
    'bid_core.score_response': 'score_response',
    'bid_core.models': 'models',
    'bid_core.config': 'config',
    'bid_core.llm_client': 'llm_client',
    'bid_core.parser': 'parser',
    'bid_core.chapter_generator': 'chapter_generator',
    'bid_core.cost_estimator': 'cost_estimator',
    'bid_core.randomizer': 'randomizer',
    'bid_core.repair': 'repair',
    'bid_core.deai': 'deai',
    # bid_technical.xxx → 根目录 xxx
    'bid_technical.generator': 'generator',
    'bid_technical.scoring_strategy': 'scoring_strategy',
    'bid_technical.evaluator_check': 'evaluator_check',
    'bid_technical.professional_database': 'professional_database',
    # 包目录映射
    'bid_technical.chapters.base': 'base',
    'bid_technical.tables.deviation_table': 'deviation_table',
    'bid_technical.tables.gantt': 'gantt',
    'bid_technical.tables.score_response_table': 'score_response_table',
}

# 虚拟包（提供子模块命名空间，需在 sys.modules 中占位）
_VIRTUAL_PACKAGES = {
    'bid_core',
    'bid_technical',
    'bid_technical.chapters',
    'bid_technical.tables',
}


class _FlatShimFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """按需解析虚拟包导入：虚拟名 → 根目录真实模块（同一对象）。"""

    _root = _ROOT

    def find_spec(self, fullname, path, target=None):
        # 虚拟包本身
        if fullname in _VIRTUAL_PACKAGES:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        # 显式映射的虚拟模块
        if fullname in _MODULE_MAP:
            return importlib.machinery.ModuleSpec(fullname, self)
        # 虚拟包下、未显式映射但根目录存在同名模块的按需子模块
        if any(fullname.startswith(p + '.') for p in _VIRTUAL_PACKAGES):
            real = fullname.rsplit('.', 1)[-1]
            if (self._root / f'{real}.py').exists():
                return importlib.machinery.ModuleSpec(fullname, self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        virt = module.__name__
        # 虚拟包：仅需提供命名空间
        if virt in _VIRTUAL_PACKAGES:
            module.__path__ = []
            module.__package__ = virt
            return
        # 解析真实模块名
        real = _MODULE_MAP.get(virt, virt.rsplit('.', 1)[-1])
        # 加载（或取回已加载的）真实模块对象 —— 关键点：完全按需，不受顺序影响
        real_mod = importlib.import_module(real)
        # 虚拟名直接指向真实模块同一对象，避免对象发散与顺序依赖问题
        sys.modules[virt] = real_mod
        # 同步属性（以防有引用持有旧的 module 对象）
        module.__dict__.update(real_mod.__dict__)
        module.__file__ = getattr(real_mod, '__file__', None)
        module.__package__ = getattr(real_mod, '__package__', virt.rsplit('.', 1)[0])


def _setup():
    """注册虚拟包占位 + 注册 MetaPathFinder（正式环境有真实包时自动跳过）。"""
    # 正式部署环境：存在真实 bid_core / bid_technical 包时跳过
    try:
        importlib.import_module('bid_core')
        return
    except ImportError:
        pass

    # 注册虚拟包占位（供子模块命名空间使用）
    for pkg in _VIRTUAL_PACKAGES:
        if pkg not in sys.modules:
            mod = types.ModuleType(pkg)
            mod.__path__ = []
            mod.__package__ = pkg
            sys.modules[pkg] = mod

    # 注册按需解析 finder
    finder = _FlatShimFinder()
    if finder not in sys.meta_path:
        sys.meta_path.insert(0, finder)


_setup()
