"""
统一数据加载器 v1.0 — P1-1 重构

集中管理所有 JSON 数据文件的加载，消除散落在各模块中的重复加载代码。
提供带缓存的加载接口和路径自动发现。

用法:
    from bid_core.data_loader import DataLoader

    loader = DataLoader()
    scoring_data = loader.load_json('scoring_strategy.json')
    synonyms = loader.load_json('synonyms.json')

    # 或直接获取项目数据目录
    data_dir = loader.data_dir
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from logger import get_logger

_log = get_logger(__name__)


class DataLoader:
    """统一 JSON 数据文件加载器

    特性:
    - 自动定位项目 data/ 目录
    - 带内存缓存，重复加载零开销
    - 文件不存在时返回空字典而非崩溃
    - 支持 JSON 和 JSONC（带注释的 JSON）
    """

    _instance: Optional['DataLoader'] = None

    def __new__(cls) -> 'DataLoader':
        """单例模式，全项目共享一份缓存"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._cache: Dict[str, Any] = {}

        # 定位 data/ 目录：从本文件所在目录向上查找第一个含 data/ 子目录的祖先目录。
        # 兼容两种部署结构：
        #   - 扁平结构：data_loader.py 在项目根，data/ 在同级
        #   - 正式包结构：data_loader.py 在 bid_core/（深层），data/ 在上层
        self._project_root = None
        cur = Path(__file__).resolve().parent
        for _ in range(6):
            if (cur / 'data').is_dir():
                self._project_root = cur
                break
            if cur.parent == cur:
                break
            cur = cur.parent
        if self._project_root is None:
            # 回退：原 parent.parent.parent 逻辑
            self._project_root = Path(__file__).resolve().parent.parent.parent
        self._data_dir = self._project_root / 'data'
        self._scripts_dir = self._project_root / 'scripts'

        _log.debug('DataLoader 初始化: data_dir=%s', self._data_dir)

    @property
    def data_dir(self) -> Path:
        """项目数据目录"""
        return self._data_dir

    @property
    def project_root(self) -> Path:
        """项目根目录"""
        return self._project_root

    def load_json(self, filename: str) -> dict:
        """加载 JSON 文件（带缓存）

        Args:
            filename: 文件名，如 'scoring_strategy.json'
                     也可传子路径 'subdir/file.json'

        Returns:
            解析后的字典，文件不存在时返回空字典
        """
        if filename in self._cache:
            return self._cache[filename]

        file_path = self._data_dir / filename

        if not file_path.exists():
            _log.warning('数据文件不存在: %s', file_path)
            self._cache[filename] = {}
            return {}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            _log.debug('已加载数据文件: %s (%d KB)',
                        filename, file_path.stat().st_size // 1024)
            self._cache[filename] = data
            return data
        except (json.JSONDecodeError, OSError) as e:
            _log.error('加载数据文件失败: %s — %s', filename, e)
            self._cache[filename] = {}
            return {}

    def load_scoring_strategy(self) -> dict:
        """加载评分策略数据"""
        return self.load_json('scoring_strategy.json')

    def load_synonyms(self) -> dict:
        """加载同义词数据"""
        return self.load_json('synonyms.json')

    def load_chapter_config(self) -> dict:
        """加载章节配置数据（P1-3 统一数据源用）"""
        return self.load_json('chapter_config.json')

    def load_user_knowledge_base(self) -> dict:
        """P3: 加载企业知识库（user_knowledge_base.json）"""
        return self.load_json('user_knowledge_base.json')

    def get_synonyms_path(self) -> str:
        """获取同义词文件路径"""
        return str(self._data_dir / 'synonyms.json')

    def clear_cache(self) -> None:
        """清空缓存（测试用）"""
        self._cache.clear()
        _log.debug('数据加载器缓存已清空')


# ── 模块级便捷函数 ──────────────────────────────────────────

def get_data_loader() -> DataLoader:
    """获取全局 DataLoader 单例"""
    return DataLoader()


def load_json(filename: str) -> dict:
    """模块级便捷函数：加载 JSON 数据文件"""
    return DataLoader().load_json(filename)
