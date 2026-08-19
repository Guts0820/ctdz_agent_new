"""图片作业提交的业务编排，不包含 FastAPI 路由。"""

import sqlite3
from typing import Any, Optional

from fastapi import HTTPException

from backend.api_gateway.models import SubmitRequest, SubmitResponse
from backend.shared.config import DATABASE_PATH, OCR_MIN_CONFIDENCE
from backend.api_gateway.services.analysis_client import analyze_submission
from backend.api_gateway.services.downstream import execute_downstream, require_fields
from backend.api_gateway.services.error_analysis_client import analyze_error
from backend.api_gateway.services.knowledge_client import retrieve_knowledge
from backend.api_gateway.services.knowledge_graph_client import fetch_question
from backend.api_gateway.services.ocr_client import recognize_submission_image
from backend.api_gateway.services.state_client import generate_review, update_state
from backend.api_gateway.services.teaching_client import check_frequency, generate_teaching


def _get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _lookup_knowledge_id(question_id: Optional[str]) -> Optional[str]:
    if not question_id:
        return None
    with _get_db() as connection:
        row = connection.execute(
            "SELECT knowledge_id FROM question_knowledge_mapping WHERE question_id = ?",
            (question_id,),
        ).fetchone()
    return row["knowledge_id"] if row else None


def _is_answer_released(question_id: str) -> bool:
    with _get_db() as connection:
        row = connection.execute(
            """
            SELECT hb.release_status FROM homework_batch_question hbq
            JOIN homework_batch hb ON hbq.batch_id = hb.batch_id
            WHERE hbq.question_id = ? ORDER BY hb.created_at DESC LIMIT 1
            """,
            (question_id,),
        ).fetchone()
        if not row:
            return True
        if row["release_status"] == "released":
            return True
        if row["release_status"] != "partial":
            return False
        return connection.execute(
            "SELECT 1 FROM question_release_override WHERE question_id = ?",
            (question_id,),
        ).fetchone() is not None


def prepare_judging_input(request: SubmitRequest) -> dict[str, Any]:
    """Build a text-only judging request from OCR and graph-owned answers."""
    ocr_data = None
    question_text = request.original_question or ""
    student_answer = request.student_write or ""
    if request.image:
        ocr_data = recognize_submission_image(request.image)
        try:
            confidence = float(ocr_data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        analysis_input = ocr_data.get("analysis_input")
        if (
            ocr_data.get("status") == "low_confidence"
            or confidence < OCR_MIN_CONFIDENCE
            or not isinstance(analysis_input, dict)
            or bool(analysis_input.get("review_required"))
        ):
            raise HTTPException(status_code=422, detail="照片模糊，请重新上传")
        question = analysis_input.get("question")
        student = analysis_input.get("student_answer")
        if not isinstance(question, dict) or not isinstance(student, dict):
            raise HTTPException(status_code=422, detail="OCR 未返回可用于判题的结构化题干和作答")
        question_text = str(question.get("text", "") or "").strip()
        student_answer = str(student.get("text", "") or "").strip()
        if not question_text:
            raise HTTPException(status_code=422, detail="OCR 未识别到可靠题干，无法匹配标准答案")
    if not question_text:
        raise HTTPException(status_code=422, detail="判题需要题干或有效的 OCR 图片")
    graph_question = fetch_question(request.question_id) if request.question_id else None
    question_id = str(graph_question.get("id", "") or "").strip() if graph_question else None
    standard_answer = str(graph_question.get("answer", "") or "").strip() if graph_question else None
    standard_solve_steps = graph_question.get("answer_steps") if graph_question else None
    if graph_question and (not question_id or not standard_answer):
        raise HTTPException(status_code=422, detail="知识图谱题目缺少可用于判题的标准答案")
    return {
        "question_id": question_id,
        "knowledge_id": str(graph_question.get("knowledge_id", "") or "").strip() or None if graph_question else None,
        "ocr_data": ocr_data,
        "analysis_request": {
            "student_id": request.student_id,
            "question_id": question_id,
            "original_question": question_text,
            "student_write": student_answer,
            "standard_answer": standard_answer,
            "standard_solve_steps": standard_solve_steps,
        },
    }


def _build_error_analysis_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "student_id": analysis.get("student_id", ""),
        "question_id": analysis.get("question_id"),
        "original_question": analysis["original_question"],
        "student_write": analysis["student_write"],
        "judge_result": analysis["judge_result"],
        "core_error_type": analysis["core_error_type"],
        "step_feedback": analysis["step_feedback"],
        "error_step_list": analysis["error_step_list"],
        "miss_step_list": analysis["miss_step_list"],
        "confidence": analysis["confidence"],
        "answer_history_id": analysis.get("answer_history_id"),
    }
def _build_teaching_payload(error_analysis: dict[str, Any], master_level: float, analysis: dict[str, Any], grade: str) -> dict[str, Any]:
    return {
        "error_tags": error_analysis["error_tags"],
        "knowledge_scope": error_analysis["knowledge_scope"],
        "knowledge_id": error_analysis.get("knowledge_id"),
        "master_level": master_level,
        "original_question": analysis["original_question"],
        "student_write": analysis["student_write"],
        "difficulty": "medium",
        "grade": grade,
        "mistake_case_id": error_analysis.get("mistake_case_id"),
    }


def process_submission(request: SubmitRequest) -> SubmitResponse:
    """Run the submission pipeline and shape the existing gateway response."""
    try:
        prepared = prepare_judging_input(request)
        analysis = execute_downstream("判题服务", lambda: analyze_submission(prepared["analysis_request"]))
        analysis = require_fields(
            "判题服务",
            analysis,
            {"judge_result", "step_feedback", "error_step_list", "miss_step_list", "is_copy", "core_error_type", "confidence", "original_question", "student_write"},
        )
        ocr_data = {}
        if prepared["ocr_data"] is not None:
            source = prepared["ocr_data"]
            ocr_data["ocr"] = {key: source.get(key) for key in ("markdown", "engine", "fallback_used", "status", "analysis_input")}
        question_id = analysis.get("question_id") or prepared["question_id"]
        if not question_id:
            raise HTTPException(status_code=422, detail="判题服务未返回匹配到的知识图谱题目")
        knowledge_id = analysis.get("knowledge_id") or prepared["knowledge_id"] or _lookup_knowledge_id(question_id)
        if analysis["judge_result"] == "correct":
            if not knowledge_id:
                return SubmitResponse(status="success", data={"judge_result": "correct", "step_feedback": analysis["step_feedback"], "master_level": 1.0, "next_action": "guide", "warning": "无法确定题目对应的知识点，跳过状态更新", **ocr_data})
            state = execute_downstream("学习状态服务", lambda: update_state(request.student_id, knowledge_id, True, analysis["confidence"]))
            state = require_fields("学习状态服务", state, {"master_level", "next_action"})
            return SubmitResponse(status="success", data={"judge_result": "correct", "step_feedback": analysis["step_feedback"], "knowledge_id": knowledge_id, "master_level": state["master_level"], "next_action": state["next_action"], **ocr_data})
        error_analysis = execute_downstream("错因分析服务", lambda: analyze_error(_build_error_analysis_payload(analysis)))
        error_analysis = require_fields(
            "错因分析服务",
            error_analysis,
            {"error_tags", "knowledge_id", "knowledge_scope", "reasoning_content", "total_confidence", "low_confidence", "fallback_used"},
        )
        knowledge_id = error_analysis.get("knowledge_id") or knowledge_id
        if not knowledge_id:
            raise HTTPException(status_code=422, detail="错因分析未能确定知识点，无法继续生成教学内容")
        knowledge_payload = {
            "knowledge_id": knowledge_id,
            "knowledge_scope": error_analysis.get("knowledge_scope", ""),
            "grade": request.grade or "三年级",
        }
        knowledge = execute_downstream("知识服务", lambda: retrieve_knowledge(knowledge_payload))
        knowledge = require_fields(
            "知识服务", knowledge, {"knowledge_explanation", "difficulty", "standard_solution", "common_errors", "teaching_tips"}
        )
        frequency = execute_downstream("教学频控服务", lambda: check_frequency(request.student_id, knowledge_id))
        frequency = require_fields("教学频控服务", frequency, {"push_permission"})
        if not frequency["push_permission"]:
            state = execute_downstream("学习状态服务", lambda: update_state(request.student_id, knowledge_id, False, error_analysis["total_confidence"]))
            state = require_fields("学习状态服务", state, {"master_level"})
            return SubmitResponse(status="success", data={"judge_result": analysis["judge_result"], "step_feedback": analysis["step_feedback"], "error_tags": error_analysis["error_tags"], "knowledge_id": knowledge_id, "knowledge_scope": error_analysis["knowledge_scope"], "knowledge_explanation": knowledge["knowledge_explanation"], "master_level": state["master_level"], "next_action": "frequency_limit_exceeded", "frequency_info": frequency, "reasoning_content": error_analysis["reasoning_content"], "low_confidence": error_analysis["low_confidence"], "fallback_used": error_analysis["fallback_used"], **ocr_data})
        state = execute_downstream("学习状态服务", lambda: update_state(request.student_id, knowledge_id, False, error_analysis["total_confidence"]))
        state = require_fields("学习状态服务", state, {"master_level", "knowledge_mastery_id", "should_generate_review", "next_action", "correct_count", "wrong_count", "mastery_status"})
        teaching = execute_downstream("教学生成服务", lambda: generate_teaching(_build_teaching_payload(error_analysis, state["master_level"], analysis, request.grade or "三年级")))
        teaching = require_fields("教学生成服务", teaching, {"explanation", "hints", "practice_list", "teaching_mode", "fallback_used"})
        review = None
        if state["should_generate_review"]:
            review = execute_downstream("复习计划服务", lambda: generate_review(request.student_id, knowledge_id, state["knowledge_mastery_id"], state["master_level"]))
            review = require_fields("复习计划服务", review, {"review_plan_id", "status"})
        fallback_used = bool(error_analysis["fallback_used"] or teaching["fallback_used"])
        response_data = {"judge_result": analysis["judge_result"], "step_feedback": analysis["step_feedback"], "error_step_list": analysis["error_step_list"], "miss_step_list": analysis["miss_step_list"], "is_copy": analysis["is_copy"], "core_error_type": analysis["core_error_type"], "confidence": analysis["confidence"], "error_tags": error_analysis["error_tags"], "reasoning_content": error_analysis["reasoning_content"], "total_confidence": error_analysis["total_confidence"], "low_confidence": error_analysis["low_confidence"], "mistake_case_id": error_analysis.get("mistake_case_id"), "knowledge_id": knowledge_id, "knowledge_scope": error_analysis["knowledge_scope"], "knowledge_explanation": knowledge["knowledge_explanation"], "difficulty": knowledge["difficulty"], "standard_solution": knowledge["standard_solution"], "common_errors": knowledge["common_errors"], "teaching_tips": knowledge["teaching_tips"], "explanation": teaching["explanation"], "guided_explanation": teaching.get("guided_explanation", ""), "final_answer_explanation": teaching.get("final_answer_explanation", ""), "hints": teaching["hints"], "practice_list": teaching["practice_list"], "teaching_mode": teaching["teaching_mode"], "fallback_used": fallback_used, "error_analysis_fallback_used": error_analysis["fallback_used"], "teaching_fallback_used": teaching["fallback_used"], "fallback_reason": teaching.get("fallback_reason"), "practice_fallback_reason": teaching.get("practice_fallback_reason"), "master_level": state["master_level"], "next_action": state["next_action"], "correct_count": state["correct_count"], "wrong_count": state["wrong_count"], "mastery_status": state["mastery_status"], "review_plan": review, **ocr_data}
        if not _is_answer_released(question_id):
            response_data.update({"final_answer_explanation": None, "explanation": teaching.get("guided_explanation", ""), "answer_released": False})
        else:
            response_data["answer_released"] = True
        return SubmitResponse(status="success", data=response_data)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail="提交编排发生未预期错误") from error
