"""
安全表达式求值模块 v1.0
用于替代 eval() 的安全替代方案

功能：
- 支持基本算术运算 (+, -, *, /, **, %)
- 支持内置数学函数 (int, round, max, min)
- 限制可用的变量和函数，防止代码注入

使用方式：
    from safe_eval import safe_eval
    result = safe_eval("area * 2 + min", {"area": 100, "min": 10})
"""

import ast
import operator
from typing import Any, Dict, Optional


# 允许的运算符映射
ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# 允许的内置函数
ALLOWED_FUNCTIONS = {
    'int': int,
    'round': round,
    'max': max,
    'min': min,
    'abs': abs,
    'float': float,
}


class SafeEvalError(Exception):
    """安全表达式求值错误"""
    
    def __init__(self, message: str, expression: str = ""):
        self.message = message
        self.expression = expression
        super().__init__(f"{message}: {expression}" if expression else message)


def safe_eval(
    expression: str,
    variables: Optional[Dict[str, Any]] = None,
    default: Any = None,
) -> Any:
    """
    安全地计算数学表达式
    
    Args:
        expression: 数学表达式字符串（如 "area * 2 + min"）
        variables: 可用变量字典（如 {"area": 100, "min": 10}）
        default: 表达式求值失败时的默认返回值
        
    Returns:
        表达式的计算结果
        
    Raises:
        SafeEvalError: 当表达式包含不安全操作时抛出
        
    Examples:
        >>> safe_eval("area * 2 + min", {"area": 100, "min": 10})
        210
        
        >>> safe_eval("max(area, min) + 5", {"area": 50, "min": 30})
        55
        
        >>> safe_eval("2 ** 3")
        8
        
        >>> # 不安全的操作会抛出异常
        >>> safe_eval("__import__('os').system('ls')")
        SafeEvalError: 不允许的操作: Call(__import__)
    """
    if not expression or not isinstance(expression, str):
        return default
    
    # 清理表达式
    expression = expression.strip()
    if not expression:
        return default
    
    try:
        # 解析为AST
        tree = ast.parse(expression, mode='eval')
        
        # 求值
        result = _eval_node(tree.body, variables or {})
        
        return result
        
    except SafeEvalError:
        raise
    except SyntaxError as e:
        raise SafeEvalError(f"语法错误: {e}", expression)
    except Exception as e:
        raise SafeEvalError(f"求值失败: {e}", expression)


def _eval_node(node: ast.AST, variables: Dict[str, Any]) -> Any:
    """
    递归求值AST节点
    
    Args:
        node: AST节点
        variables: 可用变量字典
        
    Returns:
        节点的求值结果
        
    Raises:
        SafeEvalError: 遇到不允许的节点类型时抛出
    """
    # 常量/字面量（Python 3.8+ 统一为 ast.Constant，涵盖数字/字符串等）
    if isinstance(node, ast.Constant):
        return node.value
    
    # 变量名
    if isinstance(node, ast.Name):
        name = node.id
        
        # 优先检查是否是提供的变量（变量优先于函数）
        if name in variables:
            return variables[name]
        
        # 检查是否是允许的内置函数
        if name in ALLOWED_FUNCTIONS:
            return ALLOWED_FUNCTIONS[name]
        
        raise SafeEvalError(f"未定义的变量: {name}")
        
    # 二元运算
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        
        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise SafeEvalError(f"不允许的操作符: {op_type.__name__}")
            
        return ALLOWED_OPERATORS[op_type](left, right)
    
    # 一元运算
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, variables)
        
        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise SafeEvalError(f"不允许的一元运算符: {op_type.__name__}")
            
        return ALLOWED_OPERATORS[op_type](operand)
    
    # 函数调用（仅允许白名单中的函数）
    if isinstance(node, ast.Call):
        func = _eval_node(node.func, variables)
        
        # 验证是否是允许的函数
        if func not in ALLOWED_FUNCTIONS.values():
            raise SafeEvalError(f"不允许的函数调用: {getattr(func, '__name__', str(func))}")
        
        args = [_eval_node(arg, variables) for arg in node.args]
        kwargs = {
            kw.arg: _eval_node(kw.value, variables) 
            for kw in node.keywords 
            if kw.arg is not None
        }
        
        return func(*args, **kwargs)
    
    # 拒绝其他所有节点类型
    raise SafeEvalError(
        f"不允许的操作: {node.__class__.__name__}",
        getattr(ast.dump(node), 'slice', '')[:50] if hasattr(ast.dump(node), '__getitem__') else ''
    )


def safe_eval_or_default(
    expression: str,
    variables: Optional[Dict[str, Any]] = None,
    default: Any = None,
) -> Any:
    """
    安全求值的容错版本（失败时返回默认值）
    
    Args:
        expression: 数学表达式字符串
        variables: 可用变量字典
        default: 失败时的默认返回值
        
    Returns:
        计算结果或默认值
        
    Examples:
        >>> safe_eval_or_default("area * 2", {"area": 100}, default=0)
        200
        
        >>> safe_eval_or_default("__import__('os')", default=0)
        0  # 返回默认值而非抛出异常
    """
    try:
        return safe_eval(expression, variables)
    except SafeEvalError as e:
        return default


# 导出的公共API
__all__ = [
    'safe_eval',
    'safe_eval_or_default',
    'SafeEvalError',
    'ALLOWED_FUNCTIONS',
]
