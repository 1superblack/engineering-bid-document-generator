"""logging 配置 — bidgen_v6 全项目共享日志。

用法：
    from bid_core.logger import get_logger
    log = get_logger(__name__)
    log.info('生成开始')
    log.warning('评分项覆盖率不足', extra={'coverage': 0.65})

特性：
    - 自动按模块名分流
    - 控制台彩色输出（开发）+ 文件按日轮转（生产）
    - 可通过环境变量 BIDGEN_LOG_LEVEL 调整级别
"""
import logging
import logging.handlers
import os
import sys
import tempfile
from pathlib import Path

_CONFIGURED = False
_DEFAULT_LEVEL = logging.INFO
# 默认写入系统临时目录（避免污染工作目录/发布目录）；
# 可用环境变量 BIDGEN_LOG_DIR 重定向到自定义目录。
_LOG_DIR = Path(os.environ.get('BIDGEN_LOG_DIR', str(Path(tempfile.gettempdir()) / 'bidgen_logs')))


class _ColorFormatter(logging.Formatter):
    """控制台彩色格式化器。"""

    _COLORS = {
        logging.DEBUG: '\033[36m',     # 青色
        logging.INFO: '\033[32m',      # 绿色
        logging.WARNING: '\033[33m',   # 黄色
        logging.ERROR: '\033[31m',     # 红色
        logging.CRITICAL: '\033[35m',  # 紫色
    }
    _RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelno, '')
        record.levelname = f'{color}{record.levelname:<7}{self._RESET}'
        return super().format(record)


def _configure_root() -> None:
    """配置 root logger（仅执行一次）。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.environ.get('BIDGEN_LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, level_name, _DEFAULT_LEVEL)

    root = logging.getLogger('bidgen')
    root.setLevel(level)
    root.propagate = False  # 避免向 root logger 重复传播

    fmt = '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    datefmt = '%H:%M:%S'

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(_ColorFormatter(fmt, datefmt))
    root.addHandler(console)

    # 文件 handler（按日轮转，保留 14 天）
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            _LOG_DIR / 'bidgen.log',
            when='midnight',
            backupCount=14,
            encoding='utf-8',
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(fmt, datefmt))
        root.addHandler(file_handler)
    except OSError:
        # 日志目录不可写时降级为仅控制台输出
        pass

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger。

    Args:
        name: 通常传 __name__

    Returns:
        配置好的 Logger 实例
    """
    _configure_root()
    if not name.startswith('bidgen'):
        name = f'bidgen.{name}'
    return logging.getLogger(name)
