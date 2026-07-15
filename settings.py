"""
统一配置管理模块 v1.0
集中管理所有环境变量和项目配置

功能：
- 支持环境变量覆盖
- 提供默认值和验证
- 统一LLM/日志/调试等所有配置

使用方式：
    from settings import settings
    
    if settings.llm_enable:
        client = LLMClient(api_key=settings.llm_api_key)
        
    log_level = settings.log_level
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Any


class Settings:
    """
    BidGen 全局配置
    
    所有配置项都支持通过环境变量覆盖（前缀: BIDGEN_）
    
    Examples:
        # 环境变量设置示例
        export BIDGEN_LLM_ENABLE=true
        export BIDGEN_LLM_API_KEY=sk-xxxxx
        export BIDGEN_LOG_LEVEL=DEBUG
        
        # Python中使用
        from settings import settings
        print(settings.llm_api_key)
    """
    
    def __init__(self):
        # ============ LLM 配置 ============
        self.llm_enable: bool = self._env_bool('BIDGEN_LLM_ENABLE', False)
        self.llm_api_key: str = os.environ.get('BIDGEN_LLM_API_KEY', '')
        self.llm_base_url: str = os.environ.get('BIDGEN_LLM_BASE_URL', '')
        self.llm_model: str = os.environ.get('BIDGEN_LLM_MODEL', '')
        self.llm_timeout: int = int(os.environ.get('BIDGEN_LLM_TIMEOUT', '30'))
        self.llm_max_retries: int = int(os.environ.get('BIDGEN_LLM_MAX_RETRIES', '3'))
        
        # ============ 日志配置 ============
        log_dir_env = os.environ.get('BIDGEN_LOG_DIR', '')
        self.log_dir: Path = Path(log_dir_env) if log_dir_env else Path(os.environ.get('TEMP', '/tmp')) / 'bidgen_logs'
        self.log_level: str = os.environ.get('BIDGEN_LOG_LEVEL', 'INFO').upper()
        self.log_max_bytes: int = int(os.environ.get('BIDGEN_LOG_MAX_BYTES', str(10 * 1024 * 1024)))
        self.log_backup_count: int = int(os.environ.get('BIDGEN_LOG_BACKUP_COUNT', '5'))
        self.log_format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        self.log_date_format: str = "%H:%M:%S"
        
        # ============ 调试配置 ============
        self.assembler_debug: bool = self._env_bool('BID_ASSEMBLER_DEBUG', False)
        self.debug_mode: bool = self._env_bool('BIDGEN_DEBUG', False)
        self.verbose: bool = self._env_bool('BIDGEN_VERBOSE', False)
        
        # ============ 性能配置 ============
        self.max_workers: int = int(os.environ.get('BIDGEN_MAX_WORKERS', '4'))
        self.chunk_size: int = int(os.environ.get('BIDGEN_CHUNK_SIZE', '1000'))
        self.cache_enabled: bool = self._env_bool('BIDGEN_CACHE_ENABLED', True)
        self.cache_ttl: int = int(os.environ.get('BIDGEN_CACHE_TTL', '3600'))
        
        # ============ 安全配置 ============
        self.safe_eval_enabled: bool = self._env_bool('BIDGEN_SAFE_EVAL', True)
        self.allowed_domains: List[str] = []
        self.max_file_size_mb: int = int(os.environ.get('BIDGEN_MAX_FILE_SIZE', '100'))
        
        # ============ 输出配置 ============
        self.output_dir: Path = Path("./output")
        self.output_format: str = "docx"
        self.encoding: str = "utf-8"
    
    @staticmethod
    def _env_bool(key: str, default: bool) -> bool:
        """将环境变量转换为布尔值"""
        val = os.environ.get(key, '').lower()
        if not val:
            return default
        return val in ('true', '1', 'yes', 'on')
    
    def validate_log_level(self) -> None:
        """验证日志级别是否有效"""
        allowed = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level not in allowed:
            raise ValueError(f'log_level 必须是 {allowed} 之一, 当前值: {self.log_level}')


# 全局单例实例
settings = Settings()


def get_settings() -> Settings:
    """
    获取全局配置实例
    
    Returns:
        Settings 配置对象
        
    Examples:
        >>> from settings import get_settings
        >>> config = get_settings()
        >>> print(config.log_level)
        INFO
    """
    return settings


def reload_settings() -> Settings:
    """
    重新加载配置（从环境变量）
    
    Returns:
        新的Settings实例
        
    Note:
        通常用于测试或动态修改环境变量后刷新配置
    """
    global settings
    settings = Settings()
    return settings


def print_config_summary() -> None:
    """
    打印当前配置摘要（隐藏敏感信息）
    
    Examples:
        >>> from settings import print_config_summary
        >>> print_config_summary()
        ====== BidGen 配置摘要 ======
        [LLM] enable=False, model=, timeout=30s
        [日志] level=INFO, dir=./bidgen_logs
        [性能] workers=4, cache=True
        ================================
    """
    print("\n" + "=" * 40)
    print("       BidGen 配置摘要")
    print("=" * 40)
    print(f"[LLM]     enable={settings.llm_enable}, "
          f"model={settings.llm_model or '(未配置)'}, "
          f"timeout={settings.llm_timeout}s")
    print(f"[日志]    level={settings.log_level}, "
          f"dir={settings.log_dir}")
    print(f"[性能]    workers={settings.max_workers}, "
          f"cache={settings.cache_enabled}")
    print(f"[安全]    safe_eval={settings.safe_eval_enabled}")
    print(f"[调试]    debug={settings.debug_mode}, "
          f"verbose={settings.verbose}")
    print("=" * 40 + "\n")


# 导出的公共API
__all__ = [
    'Settings',
    'settings',
    'get_settings',
    'reload_settings',
    'print_config_summary',
]
