"""
统一类型注解模块 v1.0
为bidgen项目提供标准化的类型别名和接口

功能：
- 定义常用的类型别名
- 提供Protocol基类（用于静态类型检查）
- 导出各包的公共接口

使用方式：
    from types_module import (
        TextResult,
        CheckResultDict,
        ChapterContext,
    )
"""

from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
    Protocol,
    TypeVar,
    Callable,
)

# ============ 基础类型别名 ============

# 文本处理结果
TextResult = Tuple[str, Dict[str, Any]]
"""文本处理返回值: (处理后文本, 统计信息字典)"""

# 检查结果
CheckResultDict = Dict[str, Any]
"""检查结果字典: {passed, failed, critical_issues, ...}"""

# 章节上下文
ChapterContext = Dict[str, Any]
"""章节渲染上下文: {project_info, user_context, ...}"""

# 评分项
ScoreItem = Dict[str, Union[str, float, int]]
"""评分项: {item_id, name, score, max_score, comments}"""

# 修复提示
RepairPrompt = Dict[str, str]
"""修复提示: {code, description, suggestion}"""

# 查重结果
DuplicateMatch = Dict[str, Any]
"""查重匹配: {text1, text2, similarity, location}"""

# 配置字典
ConfigDict = Dict[str, Any]
"""通用配置字典"""

# ============ 泛型变量 ============

T = TypeVar('T')
"""通用泛型变量"""

T_co = TypeVar('T_co', covariant=True)
"""协变泛型变量（只读）"""


# ============ Protocol 接口定义 ============

class TextProcessor(Protocol):
    """文本处理器接口"""
    
    def process(self, text: str) -> TextResult:
        """处理文本并返回结果"""
        ...


class Checker(Protocol):
    """检查器接口"""
    
    def check(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行检查并返回结果列表"""
        ...


class Generator(Protocol):
    """生成器接口"""
    
    def generate(self, context: ChapterContext) -> str:
        """根据上下文生成内容"""
        ...


class Scorer(Protocol):
    """评分器接口"""
    
    def score(self, item_id: str, score: float, max_score: float, comment: str = "") -> None:
        """评分单项"""
        ...
    
    def get_summary(self) -> Dict[str, Any]:
        """获取评分摘要"""
        ...


class Reporter(Protocol):
    """报告器接口"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        ...
    
    def to_text(self) -> str:
        """生成人类可读的文本报告"""
        ...


# ============ 常用回调类型 ============

ProgressCallback = Callable[[str, int, int], None]
"""进度回调: (阶段描述, 当前步骤, 总步骤)"""

LogCallback = Callable[[str], None]
"""日志回调: (日志消息)"""

ErrorCallback = Callable[[Exception], bool]
"""错误回调: (异常) -> 是否继续执行"""

ValidationFunc = Callable[[Any], bool]
"""验证函数: (值) -> 是否有效"""

TransformFunc = Callable[[Any], T]
"""转换函数: (输入) -> 输出"""


# ============ 导出列表 ============

__all__ = [
    # 基础类型
    'TextResult',
    'CheckResultDict',
    'ChapterContext',
    'ScoreItem',
    'RepairPrompt',
    'DuplicateMatch',
    'ConfigDict',
    # 泛型
    'T',
    'T_co',
    # 协议
    'TextProcessor',
    'Checker',
    'Generator',
    'Scorer',
    'Reporter',
    # 回调
    'ProgressCallback',
    'LogCallback',
    'ErrorCallback',
    'ValidationFunc',
    'TransformFunc',
]
