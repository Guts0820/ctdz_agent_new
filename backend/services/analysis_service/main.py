"""Text-only judging service backed by knowledge-graph standard answers."""

import json
import os
import sqlite3
import sys
import unicodedata
import ast
import hashlib
import operator
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import requests

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


SERVICE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SERVICE_DIR.parents[1]
sys.path.insert(0, str(SERVICE_DIR))
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.shared.config import DATABASE_PATH
from backend.shared.observability import log_event, timed
from backend.shared.id_utils import generate_id
from backend.services.analysis_service.llm_judge import (
    LlmJudgeResult,
    judge_unseen_question_with_llm,
    judge_with_llm,
)
from backend.services.analysis_service.question_retrieval import resolve_question_reference
from backend.shared.config import KNOWLEDGE_GRAPH_URL, HTTP_TIMEOUT_SECONDS


app = FastAPI(title="Judging Service", version="1.0.0")
DATABASE = DATABASE_PATH


class AnalysisRequest(BaseModel):
    student_id: str
    question_id: Optional[str] = None
    original_question: str
    student_write: str = ""
    standard_answer: Optional[str] = None
    standard_solve_steps: Optional[str] = None


class AnalysisResponse(BaseModel):
    judge_result: str
    step_feedback: str
    error_step_list: List[str]
    miss_step_list: List[str]
    is_copy: bool
    core_error_type: str
    confidence: float
    original_question: str
    student_write: str
    text_status: str
    student_id: str
    question_id: Optional[str] = None
    knowledge_id: Optional[str] = None
    answer_history_id: Optional[str] = None
    question_match_confidence: Optional[float] = None
    question_match_reason: Optional[str] = None
    ocr_markdown: Optional[str] = None
    ocr_engine: Optional[str] = None
    ocr_fallback_used: Optional[bool] = None
    ocr_status: Optional[str] = None
    ocr_analysis_input: Optional[dict] = None
    standard_answer: Optional[str] = None
    standard_solve_steps: Optional[str] = None
    question_source: Optional[str] = None
    question_pending_review: bool = False


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def normalize_answer(answer: str) -> str:
    """Normalize superficial formatting without changing mathematical meaning."""
    normalized = unicodedata.normalize("NFKC", answer).strip()
    normalized = normalized.replace("×", "*").replace("÷", "/")
    return "".join(normalized.split())


_ARITHMETIC_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _evaluate_arithmetic_expression(expression: str) -> float:
    node = ast.parse(expression, mode="eval").body

    def evaluate(current: ast.AST) -> float:
        if isinstance(current, ast.Constant) and isinstance(current.value, (int, float)):
            return float(current.value)
        if isinstance(current, ast.UnaryOp) and isinstance(current.op, ast.USub):
            return -evaluate(current.operand)
        if isinstance(current, ast.BinOp) and type(current.op) in _ARITHMETIC_OPERATORS:
            return _ARITHMETIC_OPERATORS[type(current.op)](evaluate(current.left), evaluate(current.right))
        raise ValueError("unsupported arithmetic expression")

    return evaluate(node)


def _judge_simple_arithmetic(question: str, student_answer: str) -> Optional[dict]:
    """Local fallback for an OCR stem that is only a numeric expression."""
    normalized = unicodedata.normalize("NFKC", question).replace("×", "*").replace("÷", "/")
    match = re.search(r"(?<![\d.])[-+()\d.*/]+(?:\s*=\s*[-+()\d.*/]+)?", normalized)
    if not match:
        return None
    expression = match.group(0).split("=", 1)[0].strip()
    if not expression or not re.fullmatch(r"[-+()\d.*/\s]+", expression):
        return None
    try:
        result = _evaluate_arithmetic_expression(expression)
    except (SyntaxError, ValueError, ZeroDivisionError):
        return None
    standard_answer = str(int(result)) if result.is_integer() else format(result, ".12g")
    student_normalized = normalize_answer(student_answer)
    try:
        is_correct = abs(float(student_normalized) - result) < 1e-9
    except ValueError:
        is_correct = student_normalized == standard_answer
    return {
        "standard_answer": standard_answer,
        "standard_solve_steps": f"计算 {expression} = {standard_answer}。",
        "judge_result": "correct" if is_correct else "wrong",
        "step_feedback": "回答正确。" if is_correct else "计算结果与正确答案不一致。",
        "error_step_list": [] if is_correct else ["计算结果不一致"],
        "miss_step_list": [],
        "core_error_type": "" if is_correct else "计算结果错误",
        "confidence": 1.0,
    }


def _rule_based_judgment(
    question: str,
    student_answer: str,
    standard_answer: str,
) -> dict:
    """Deterministic fallback used when the module LLM is unavailable."""
    normalized_student_answer = normalize_answer(student_answer)
    normalized_standard_answer = normalize_answer(standard_answer)
    if not normalized_student_answer:
        return {
            "judge_result": "unknown",
            "step_feedback": "未识别到学生作答。",
            "error_step_list": [],
            "miss_step_list": ["未作答"],
            "is_copy": False,
            "core_error_type": "未作答",
            "confidence": 1.0,
            "original_question": question,
            "student_write": student_answer,
            "text_status": "normal",
        }

    is_correct = normalized_student_answer == normalized_standard_answer
    return {
        "judge_result": "correct" if is_correct else "wrong",
        "step_feedback": "答案正确。" if is_correct else "答案与标准答案不一致。",
        "error_step_list": [] if is_correct else ["最终答案与标准答案不一致"],
        "miss_step_list": [],
        "is_copy": False,
        "core_error_type": "" if is_correct else "答案不一致",
        "confidence": 1.0,
        "original_question": question,
        "student_write": student_answer,
        "text_status": "normal",
    }


def judge_against_standard_answer(
    question: str,
    student_answer: str,
    standard_answer: str,
    standard_solve_steps: Optional[str] = None,
) -> dict:
    """Judge against the graph-owned answer, using this service's LLM first."""
    if not normalize_answer(student_answer):
        return _rule_based_judgment(question, student_answer, standard_answer)

    try:
        llm_result = LlmJudgeResult.model_validate(
            judge_with_llm(
                question=question,
                student_answer=student_answer,
                standard_answer=standard_answer,
                standard_solve_steps=standard_solve_steps,
            )
        ).model_dump()
    except Exception:
        # The deterministic path keeps the service available when the external model
        # is not configured or returns an invalid response.
        return _rule_based_judgment(question, student_answer, standard_answer)

    llm_result.update(
        {
            "original_question": question,
            "student_write": student_answer,
            "is_copy": False,
            "text_status": "normal",
        }
    )
    if llm_result["judge_result"] == "correct":
        llm_result.update({"error_step_list": [], "miss_step_list": [], "core_error_type": ""})
    return llm_result


def _upsert_unseen_question(question: str, answer: str, steps: str) -> dict:
    response = requests.post(
        f"{KNOWLEDGE_GRAPH_URL.rstrip('/')}/internal/api/questions/standard-answer",
        json={"items": [{"text": question, "answer": answer, "explanation": steps}]},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    questions = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(questions, list) or not questions or not isinstance(questions[0], dict):
        raise ValueError("题库写入接口返回格式错误")
    return questions[0]


def _upsert_unseen_question_locally(question: str, answer: str, steps: str) -> dict:
    """Persist a pending question when Neo4j is temporarily unavailable."""
    question_id = f"TQ{hashlib.sha256(question.encode('utf-8')).hexdigest()[:12].upper()}"
    with get_db() as connection:
        existing = connection.execute(
            "SELECT question_id FROM question WHERE question_description = ? LIMIT 1",
            (question,),
        ).fetchone()
        if existing:
            question_id = str(existing["question_id"])
        else:
            connection.execute(
                """INSERT INTO question (
                    question_id, question_description, question_type, difficulty,
                    standard_solve_steps, answer
                ) VALUES (?, ?, '待审核', 'unknown', ?, ?)""",
                (question_id, question, steps, answer),
            )
            connection.commit()
    return {"id": question_id, "knowledge_id": None}


@app.post("/internal/api/v1/analysis/process", response_model=AnalysisResponse)
@timed("analysis.process")
def process_analysis(request: AnalysisRequest) -> AnalysisResponse:
    """Resolve the graph reference, then judge against its standard answer."""
    log_event("analysis.request", student_id=request.student_id, question_id=request.question_id)
    if not request.original_question.strip():
        raise HTTPException(status_code=422, detail="OCR 未返回可用于检索的题干")

    question_id = request.question_id
    knowledge_id = None
    question_match_confidence = None
    question_match_reason = None
    standard_answer = (request.standard_answer or "").strip()
    standard_solve_steps = request.standard_solve_steps
    if not standard_answer:
        graph_available = True
        try:
            match = resolve_question_reference(request.original_question)
        except Exception:
            graph_available = False
            match = None
        if match is None:
            # 学生提交不能创建正式题库题目，也不能触发未知题标准解题。
            # 只有教师题目录入流程允许建立新的 canonical question。
            if not graph_available:
                raise HTTPException(status_code=503, detail="题库检索服务暂不可用，请稍后重试")
            raise HTTPException(status_code=422, detail="题目不在题库中")
        else:
            matched_question = match["question"]
            question_id = match["question_id"]
            knowledge_id = match.get("knowledge_id")
            question_match_confidence = match["match_confidence"]
            question_match_reason = match["match_reason"]
            standard_answer = str(matched_question.get("answer", "") or "").strip()
            standard_solve_steps = matched_question.get("answer_steps")
            source = "knowledge_graph"
        if not standard_answer:
            raise HTTPException(status_code=422, detail="知识图谱题目缺少标准答案，无法判题")
    else:
        source = "provided"

    process_result = judge_against_standard_answer(
        question=request.original_question,
        student_answer=request.student_write,
        standard_answer=standard_answer,
        standard_solve_steps=standard_solve_steps,
    )

    answer_history_id = generate_id("AH")
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO answer_history (
                answer_history_id, student_id, question_id, submit_type, submit_count,
                ocr_question, student_ocr_answer, student_ocr_steps, is_correct,
                judge_result, step_feedback, error_step_list, miss_step_list,
                is_copy, core_error_type, confidence, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                answer_history_id,
                request.student_id,
                question_id,
                "首次错题",
                1,
                process_result["original_question"],
                process_result["student_write"],
                "",
                process_result["judge_result"] == "correct",
                process_result["judge_result"],
                process_result["step_feedback"],
                json.dumps(process_result["error_step_list"], ensure_ascii=False),
                json.dumps(process_result["miss_step_list"], ensure_ascii=False),
                process_result["is_copy"],
                process_result["core_error_type"],
                process_result["confidence"],
                datetime.now().isoformat(),
            ),
        )
        connection.commit()

    process_result.update(
        {
            "student_id": request.student_id,
            "question_id": question_id,
            "knowledge_id": knowledge_id,
            "answer_history_id": answer_history_id,
            "question_match_confidence": question_match_confidence,
            "question_match_reason": question_match_reason,
            "ocr_markdown": None,
            "ocr_engine": None,
            "ocr_fallback_used": None,
            "ocr_status": None,
            "ocr_analysis_input": None,
            "standard_answer": standard_answer,
            "standard_solve_steps": standard_solve_steps,
            "question_source": source,
            "question_pending_review": source.startswith(("llm_new_question", "rule_new_question")),
        }
    )
    return AnalysisResponse(**process_result)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "Judging Service",
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
