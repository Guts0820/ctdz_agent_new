"""Text-only judging service backed by knowledge-graph standard answers."""

import json
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


SERVICE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SERVICE_DIR.parents[1]
sys.path.insert(0, str(SERVICE_DIR))
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.shared.config import DATABASE_PATH
from backend.shared.observability import log_event, timed
from backend.shared.id_utils import generate_id
from backend.services.analysis_service.llm_judge import LlmJudgeResult, judge_with_llm
from backend.services.analysis_service.question_retrieval import resolve_question_reference


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
    question_match_confidence: Optional[float] = None
    question_match_reason: Optional[str] = None
    ocr_markdown: Optional[str] = None
    ocr_engine: Optional[str] = None
    ocr_fallback_used: Optional[bool] = None
    ocr_status: Optional[str] = None
    ocr_analysis_input: Optional[dict] = None


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def normalize_answer(answer: str) -> str:
    """Normalize superficial formatting without changing mathematical meaning."""
    normalized = unicodedata.normalize("NFKC", answer).strip()
    normalized = normalized.replace("×", "*").replace("÷", "/")
    return "".join(normalized.split())


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
        try:
            match = resolve_question_reference(request.original_question)
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"知识图谱检索服务暂不可用：{error}") from error
        if match is None:
            raise HTTPException(status_code=422, detail="未能可靠匹配知识图谱中的标准题目，无法判题")
        matched_question = match["question"]
        question_id = match["question_id"]
        knowledge_id = match.get("knowledge_id")
        question_match_confidence = match["match_confidence"]
        question_match_reason = match["match_reason"]
        standard_answer = str(matched_question.get("answer", "") or "").strip()
        standard_solve_steps = matched_question.get("answer_steps")
        if not standard_answer:
            raise HTTPException(status_code=422, detail="知识图谱题目缺少标准答案，无法判题")

    process_result = judge_against_standard_answer(
        question=request.original_question,
        student_answer=request.student_write,
        standard_answer=standard_answer,
        standard_solve_steps=standard_solve_steps,
    )

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
                generate_id("AH"),
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
            "question_match_confidence": question_match_confidence,
            "question_match_reason": question_match_reason,
            "ocr_markdown": None,
            "ocr_engine": None,
            "ocr_fallback_used": None,
            "ocr_status": None,
            "ocr_analysis_input": None,
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
