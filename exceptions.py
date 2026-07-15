"""
统一异常体系 v1.0
为bidgen项目提供标准化的异常类型

功能：
- 定义异常层次结构
- 支持异常链和上下文信息
- 便于错误处理和日志记录

使用方式：
    from exceptions import (
        BidGenError,
        ConfigurationError,
        GenerationError,
        ValidationError,
    )
    
    try:
        generate_bid(project_info)
    except ValidationError as e:
        log.error(f"验证失败: {e}")
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class BidGenError(Exception):
    """
    基础异常类
    
    所有bidgen异常的基类，支持上下文信息和异常链。
    
    Attributes:
        message: 异常消息
        context: 额外的上下文字典
        code: 错误代码（可选）
        
    Examples:
        >>> raise BidGenError("生成失败", code="GEN001")
        >>> raise BidGenError("处理错误", context={"file": "test.docx"})
    """
    
    def __init__(
        self,
        message: str = "",
        code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        self.message = message
        self.code = code
        self.context = context or {}
        # v8.1: 子类传递的额外关键字参数自动放入 context
        for k, v in kwargs.items():
            self.context[k] = v
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """格式化完整的错误消息"""
        parts = []
        if self.code:
            parts.append(f"[{self.code}]")
        if self.message:
            parts.append(self.message)
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in list(self.context.items())[:3])
            parts.append(f"({ctx_str})")
        return " ".join(parts)
    
    def with_context(self, **kwargs) -> 'BidGenError':
        """
        添加上下文信息并返回新的异常
        
        Examples:
        >>> error = BidGenError("生成失败")
        >>> new_error = error.with_context(file="test.docx", page=5)
        """
        new_context = {**self.context, **kwargs}
        return type(self)(
            message=self.message,
            code=self.code,
            context=new_context,
        )


# ============ 配置相关异常 ============

class ConfigurationError(BidGenError):
    """
    配置错误

    当配置缺失、无效或冲突时抛出。

    Examples:
        >>> raise ConfigurationError("LLM API Key未配置")
        >>> raise ConfigurationError("配置文件不存在", path="config.json")
    """

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('code', 'CONFIG')
        super().__init__(message, **kwargs)


# ============ 生成相关异常 ============

class GenerationError(BidGenError):
    """
    生成错误
    
    当标书生成过程中发生错误时抛出。
    
    Examples:
        >>> raise GenerationError("章节渲染失败", chapter="技术方案")
        >>> raise GenerationError("图片插入失败", image_path="/path/to/img.png")
    """
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)


class ChapterGenerationError(GenerationError):
    """
    章节生成错误
    
    特定于单个章节的生成失败。
    """
    
    def __init__(
        self,
        message: str,
        chapter_name: Optional[str] = None,
        **kwargs
    ):
        if chapter_name:
            kwargs['chapter'] = chapter_name
        super().__init__(message, **kwargs)


class TableGenerationError(GenerationError):
    """
    表格生成错误
    
    特定于表格渲染的失败。
    """
    
    def __init__(
        self,
        message: str,
        table_name: Optional[str] = None,
        **kwargs
    ):
        if table_name:
            kwargs['table'] = table_name
        super().__init__(message, **kwargs)


# ============ 验证相关异常 ============

class ValidationError(BidGenError):
    """
    验证错误

    当输入数据不符合预期格式或规则时抛出。

    Examples:
        >>> raise ValidationError("project_info 缺少必填字段: name")
        >>> raise ValidationError("日期格式错误", field="start_date")
    """

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('code', 'VALID')
        super().__init__(message, **kwargs)


class MissingRequiredFieldError(ValidationError):
    """
    必填字段缺失错误
    
    特指缺少必要的输入字段。
    """
    
    def __init__(self, field_name: str, **kwargs):
        super().__init__(
            f"缺少必填字段: {field_name}",
            field=field_name,
            code="MISSING_FIELD",
            **kwargs
        )


# ============ 外部服务相关异常 ============

class ExternalServiceError(BidGenError):
    """
    外部服务错误
    
    当调用外部服务（如LLM API）失败时抛出。
    
    Examples:
        >>> raise ExternalServiceError("LLM请求超时", service="openai")
        >>> raise ExternalServiceError("API限流", status_code=429)
    """
    
    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        if service:
            kwargs['service'] = service
        if status_code:
            kwargs['status_code'] = str(status_code)
        super().__init__(message, **kwargs)


class LLMError(ExternalServiceError):
    """
    LLM服务错误
    
    特指LLM相关的服务错误。
    """
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service="llm", code="LLM", **kwargs)


# ============ 文件/IO相关异常 ============

class FileOperationError(BidGenError):
    """
    文件操作错误
    
    当文件读取、写入或转换时出错。
    
    Examples:
        >>> raise FileOperationError("文件不存在", path="input.docx")
        >>> raise FileOperationError("权限不足", operation="write")
    """
    
    def __init__(
        self,
        message: str,
        path: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        if path:
            kwargs['path'] = path
        if operation:
            kwargs['operation'] = operation
        super().__init__(message, **kwargs)


# ============ 检查/评审相关异常 ============

class CheckError(BidGenError):
    """
    检查过程错误
    
    当标书检查过程中出现问题时抛出。
    """
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)


# ============ 导出列表 ============

__all__ = [
    # 基础异常
    'BidGenError',
    # 配置
    'ConfigurationError',
    # 生成
    'GenerationError',
    'ChapterGenerationError',
    'TableGenerationError',
    # 验证
    'ValidationError',
    'MissingRequiredFieldError',
    # 外部服务
    'ExternalServiceError',
    'LLMError',
    # 文件操作
    'FileOperationError',
    # 检查
    'CheckError',
]
