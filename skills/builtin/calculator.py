"""Calculator skill - safe math expression evaluator."""

from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult

# Safe operators supported
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Safe math functions
_SAFE_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "log": math.log, "log10": math.log10, "log2": math.log2,
    "exp": math.exp, "abs": abs, "ceil": math.ceil, "floor": math.floor,
    "round": round, "pi": math.pi, "e": math.e,
    "factorial": math.factorial,
}

_ZH_NUM = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100, "千": 1000, "萬": 10000, "億": 100000000,
}


def _safe_eval(node: ast.expr) -> float:
    """Recursively evaluate a safe AST node."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant: {node.value}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _OPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if op_type == ast.Pow and abs(right) > 300:
            raise ValueError("Exponent too large (max 300)")
        result = _OPS[op_type](left, right)
        return result
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _OPS[op_type](_safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls allowed")
        func_name = node.func.id
        if func_name not in _SAFE_FUNCS:
            raise ValueError(f"Unknown function: {func_name}")
        func = _SAFE_FUNCS[func_name]
        args = [_safe_eval(a) for a in node.args]
        return func(*args)
    elif isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCS:
            val = _SAFE_FUNCS[node.id]
            if isinstance(val, (int, float)):
                return float(val)
        raise ValueError(f"Unknown variable: {node.id}")
    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")


class CalculatorSkill(BaseSkill):
    name = "calculator"
    description = "計算機 — 安全數學運算（支援四則、次方、三角函數、對數）"
    triggers = [
        "計算", "算", "calculator", "math", "計算機",
        "幾乘", "幾加", "幾除", "幾減", "等於多少",
        "+", "×", "÷",
    ]
    intent_patterns = [
        r"\d+\s*[\+\-\*\/\^%]\s*\d+",          # 3 + 4, 10 * 5
        r"(計算|算).{0,5}[\d\(]",               # 計算 123+456
        r"\d+\s*(乘以|除以|加上|減去|次方)\s*\d+",  # 3 乘以 4
        r"(sqrt|sin|cos|tan|log|factorial)\s*\(",  # sqrt(16)
        r"\d+的\d+次方",                         # 2的10次方
        r"(多少|等於|結果是).{0,10}\d",           # 等於多少
        r"\d+\s*(percent|%)\s*(of|的)\s*\d+",   # 20% of 500
    ]
    category = "utility"
    requires_llm = False

    instructions = (
        "計算機支援：\n"
        "1. 基本運算：「3 + 4 * 2」「(10 + 5) / 3」\n"
        "2. 次方：「2 ^ 10」「2的10次方」\n"
        "3. 函數：「sqrt(144)」「sin(pi/2)」「log(100)」\n"
        "4. 百分比：「20% of 500」"
    )

    # Patterns to extract expression from natural language
    _ZH_OP = {
        "乘以": "*", "乘": "*", "×": "*",
        "除以": "/", "除": "/", "÷": "/",
        "加上": "+", "加": "+",
        "減去": "-", "減": "-",
        "次方": "**", "的次方": "**",
        "^": "**",
    }

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        expr = self._extract_expression(query)
        if not expr:
            return SkillResult(
                content="請輸入數學運算式，例如：「計算 3 + 4 * 2」或「sqrt(144)」",
                success=False, source=self.name,
            )

        try:
            result = self._evaluate(expr)
            # Format result nicely
            if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
                result_str = str(int(result))
            else:
                result_str = f"{result:.6g}"

            return SkillResult(
                content=f"🔢 **{expr} = {result_str}**",
                success=True, source=self.name,
            )
        except ZeroDivisionError:
            return SkillResult(content="❌ 錯誤：除以零", success=False, source=self.name)
        except (ValueError, SyntaxError) as e:
            return SkillResult(content=f"❌ 計算錯誤：{e}", success=False, source=self.name)
        except Exception as e:
            return SkillResult(content=f"❌ 無法計算：{e}", success=False, source=self.name)

    def _extract_expression(self, text: str) -> str | None:
        """Extract math expression from natural language query."""
        # Remove trigger words
        for t in ["計算", "計算機", "calculator", "math", "算一下", "幫我算", "幫我計算", "請計算"]:
            text = text.replace(t, "").strip()

        # Replace Chinese operators
        for zh, op in self._ZH_OP.items():
            text = text.replace(zh, op)

        # Handle "X的Y次方"
        text = re.sub(r'(\d+)的(\d+)\*\*', r'\1**\2', text)
        text = re.sub(r'(\d+)的(\d+)次方', r'\1**\2', text)

        # Handle percentage: "20% of 500" -> "0.20 * 500"
        text = re.sub(r'(\d+(?:\.\d+)?)\s*%\s*(of|的)\s*(\d+(?:\.\d+)?)',
                      lambda m: str(float(m.group(1)) / 100 * float(m.group(3))), text)

        # Remove units and filler text, keep math chars
        # Allow: digits, operators, parentheses, decimal, spaces, math func names
        allowed = re.sub(r'[^\d\+\-\*\/\(\)\.\,\s\^sqrtsincotaglbpief]', ' ', text)
        # Restore function names
        for func in ["sqrt", "sin", "cos", "tan", "log", "exp", "abs", "ceil", "floor",
                     "factorial", "pi", "e", "asin", "acos", "atan"]:
            if func in text:
                # already preserved by allowed chars
                pass
        allowed = allowed.strip()

        # Validate: must contain at least one digit
        if not re.search(r'\d', allowed):
            return None

        return allowed.strip() if allowed else None

    def _evaluate(self, expr: str) -> float:
        """Safely evaluate a math expression string."""
        # Normalize: replace ^ with **
        expr = expr.replace("^", "**")
        # Remove any remaining non-math characters
        # Allow digits, operators, parens, decimal, spaces, letters (for func names)
        clean = re.sub(r'[^\d\+\-\*\/\(\)\.\s\_a-zA-Z,]', '', expr).strip()
        if not clean:
            raise ValueError("Empty expression")

        try:
            tree = ast.parse(clean, mode='eval')
        except SyntaxError as e:
            raise SyntaxError(f"無效的運算式: {clean}") from e

        return _safe_eval(tree.body)
