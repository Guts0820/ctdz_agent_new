import ast
import re
import unicodedata
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, Field

from backend.shared.llm_client import call_llm_json


class AnswerComparison(BaseModel):
    status: Literal["agreed", "conflict", "uncertain"]
    confidence: float = Field(ge=0, le=1)
    reason: str


class _LlmComparison(BaseModel):
    equivalent: bool
    confidence: float = Field(ge=0, le=1)
    reason: str = ""


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").strip().lower()
    normalized = normalized.replace("×", "*").replace("÷", "/").replace("−", "-")
    normalized = re.sub(r"[,，。；;、]+", "|", normalized)
    return re.sub(r"\s+", "", normalized).strip("|")


def _evaluate_expression(value: str) -> Fraction | None:
    expression = _normalize_text(value)
    expression = re.sub(r"(?<=\d)(?:元|米|厘米|毫米|千米|克|千克|人|个|本|支|只)$", "", expression)
    if expression.endswith("%"):
        expression = f"({expression[:-1]})/100"
    if not expression or not re.fullmatch(r"[-+*/().\d]+", expression):
        return None
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None

    def visit(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Fraction(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            return left / right
        raise ValueError("unsupported expression")

    try:
        return visit(tree)
    except (ValueError, ZeroDivisionError):
        return None


def compare_answers(teacher_answer: str, solved_answer: str) -> AnswerComparison:
    teacher_normalized = _normalize_text(teacher_answer)
    solved_normalized = _normalize_text(solved_answer)
    if teacher_normalized == solved_normalized:
        return AnswerComparison(status="agreed", confidence=1.0, reason="规范化后答案一致")

    teacher_value = _evaluate_expression(teacher_answer)
    solved_value = _evaluate_expression(solved_answer)
    if teacher_value is not None and solved_value is not None:
        if teacher_value == solved_value:
            return AnswerComparison(status="agreed", confidence=1.0, reason="数学表达式数值等价")
        return AnswerComparison(status="conflict", confidence=1.0, reason="数学表达式计算结果不一致")

    try:
        payload = call_llm_json(
            "你是小学数学答案等价性校验器。只判断两个答案是否表达同一结果，返回严格 JSON。",
            (
                "比较以下两个答案，返回 "
                '{"equivalent": true或false, "confidence": 0到1, "reason": "简短原因"}。\n'
                f"教师答案：{teacher_answer}\n系统解答：{solved_answer}"
            ),
        )
        result = _LlmComparison.model_validate(payload)
    except Exception:
        return AnswerComparison(status="uncertain", confidence=0.0, reason="无法可靠判断答案是否等价")
    if result.confidence < 0.8:
        return AnswerComparison(status="uncertain", confidence=result.confidence, reason=result.reason or "比较置信度不足")
    return AnswerComparison(
        status="agreed" if result.equivalent else "conflict",
        confidence=result.confidence,
        reason=result.reason or ("答案语义等价" if result.equivalent else "答案语义不一致"),
    )
