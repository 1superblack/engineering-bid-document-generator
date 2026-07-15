"""
统一日志管理模块 v1.0
为新拆分的包提供标准化的日志接口

功能：
- 自动创建以包名为名称的logger
- 提供装饰器简化函数级日志记录
- 支持结构化日志输出

使用方式：
    from log_helper import get_logger, log_call
    
    logger = get_logger(__name__)
    
    @log_call(logger)
    def process_text(text):
        # 函数执行时自动记录入口和出口
        return text
"""

import logging
import functools
import time
from typing import Any, Callable, Optional


def get_logger(name: str) -> logging.Logger:
    """
    获取标准化的logger实例
    
    Args:
        name: 通常传入 __name__
        
    Returns:
        配置好的logger实例
        
    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("处理开始")
    """
    logger = logging.getLogger(name)
    
    # 如果logger还没有处理器，添加默认配置（仅一次）
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    
    return logger


def log_call(
    logger: logging.Logger,
    level: int = logging.DEBUG,
    include_args: bool = False,
    include_result: bool = False,
) -> Callable:
    """
    函数调用日志装饰器
    
    Args:
        logger: logger实例
        level: 日志级别（默认DEBUG）
        include_args: 是否记录函数参数
        include_result: 是否记录返回值（截断到100字符）
        
    Returns:
        装饰器函数
        
    Examples:
        >>> @log_call(logger, include_args=True)
        ... def process(text):
        ...     return text.upper()
        >>> 
        >>> result = process("hello")
        # 输出: [DEBUG] module: 调用 process(args=('hello',))
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            func_name = func.__name__
            
            # 记录调用信息
            if include_args:
                args_str = f"args={args}, kwargs={kwargs}"
                if len(str(args_str)) > 200:
                    args_str = str(args_str)[:200] + "..."
                logger.log(level, f"[{func_name}] 入口 | {args_str}")
            else:
                logger.log(level, f"[{func_name}] 入口")
            
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                elapsed_ms = (time.time() - start_time) * 1000
                
                if include_result and result is not None:
                    result_str = str(result)[:100]
                    logger.log(level, f"[{func_name}] 出口 ({elapsed_ms:.1f}ms) | {result_str}")
                else:
                    logger.log(level, f"[{func_name}] 出口 ({elapsed_ms:.1f}ms)")
                
                return result
                
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.error(f"[{func_name}] 异常 ({elapsed_ms:.1f}ms) | {type(e).__name__}: {e}")
                raise
                
        return wrapper
    return decorator


def log_performance(
    logger: logging.Logger,
    threshold_ms: float = 100.0,
) -> Callable:
    """
    性能监控装饰器（只记录超过阈值的慢调用）
    
    Args:
        logger: logger实例
        threshold_ms: 阈值（毫秒），超过此值才记录警告
        
    Returns:
        装饰器函数
        
    Examples:
        >>> @log_performance(logger, threshold_ms=50)
        ... def slow_operation():
        ...     time.sleep(0.1)  # 100ms
        >>> 
        >>> slow_operation()
        # 输出: [WARNING] module: slow_operation 执行耗时 100.2ms (>50ms阈值)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000
            
            if elapsed_ms > threshold_ms:
                logger.warning(
                    f"[{func.__name__}] 慢调用警告 "
                    f"| 耗时 {elapsed_ms:.1f}ms (>{threshold_ms}ms阈值)"
                )
            
            return result
        return wrapper
    return decorator


# 导出的公共API
__all__ = [
    'get_logger',
    'log_call',
    'log_performance',
]
