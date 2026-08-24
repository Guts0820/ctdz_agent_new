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


def _ensure_question_knowledge_mapping(question_id: str, knowledge_id: str) -> None:
    """Persist an authoritative analysis mapping once, without replacing an existing mapping."""
    from backend.shared.id_utils import generate_id

    with _get_db() as connection:
        existing = connection.execute(
            "SELECT knowledge_id FROM question_knowledge_mapping WHERE question_id = ? LIMIT 1",
            (question_id,),
        ).fetchone()
        if existing is None:
            connection.execute(
                """INSERT INTO question_knowledge_mapping
                   (qkm_id, question_id, knowledge_id, mapping_weight) VALUES (?, ?, ?, 1.0)""",
                (generate_id("QKM"), question_id, knowledge_id),
            )
            connection.commit()


def _batch_question_ids(batch_id: Optional[str]) -> Optional[list[str]]:
    if not batch_id:
        return None
    with _get_db() as connection:
        rows = connection.execute(
            "SELECT question_id FROM homework_batch_question WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"作业批次不存在或未分配题目: {batch_id}")
    return [str(row["question_id"]) for row in rows]


def _is_answer_released(question_id: str, batch_id: Optional[str] = None) -> bool:
    try:
        with _get_db() as connection:
            row = connection.execute(
                """
                SELECT hb.release_status, hb.batch_id FROM homework_batch_question hbq
                JOIN homework_batch hb ON hbq.batch_id = hb.batch_id
                WHERE hbq.question_id = ?
                  AND (? IS NULL OR hb.batch_id = ?)
                ORDER BY hb.created_at DESC LIMIT 1
                """,
                (question_id, batch_id, batch_id),
            ).fetchone()
            if not row:
                return True
            if row["release_status"] == "released":
                return True
            if row["release_status"] != "partial":
                return False
            return connection.execute(
                "SELECT 1 FROM question_release_override WHERE batch_id = ? AND question_id = ?",
                (row["batch_id"], question_id),
            ).fetchone() is not None
    except Exception as error:
        print(f"[gateway] 答案放行状态查询失败，按 locked 处理: {error}")
        return False


def _ensure_mistake_case(student_id: str, question_id: Optional[str], answer_history_id: Optional[str]) -> str:
    """Keep an unmatched wrong answer in the mistake book without inventing a cause."""
    from backend.shared.id_utils import generate_id

    with _get_db() as connection:
        existing = None
        if question_id:
            existing = connection.execute(
                """SELECT mistake_case_id FROM mistake_case
                   WHERE student_id = ? AND question_id = ?
                   ORDER BY created_at ASC LIMIT 1""",
                (student_id, question_id),
            ).fetchone()
        mistake_case_id = existing["mistake_case_id"] if existing else generate_id("MC")
        if existing:
            connection.execute(
                "UPDATE mistake_case SET current_status = 'correcting' WHERE mistake_case_id = ?",
                (mistake_case_id,),
            )
        else:
            connection.execute(
                "INSERT INTO mistake_case (mistake_case_id, student_id, question_id, current_status) VALUES (?, ?, ?, ?)",
                (mistake_case_id, student_id, question_id, "correcting"),
            )
        if answer_history_id:
            connection.execute(
                "UPDATE answer_history SET mistake_case_id = ? WHERE answer_history_id = ?",
                (mistake_case_id, answer_history_id),
            )
        connection.commit()
    return mistake_case_id


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
        if not isinstance(analysis_input, dict):
            raise HTTPException(status_code=422, detail="OCR 未返回结构化识别结果，请重新上传清晰、完整的照片")
        question = analysis_input.get("question")
        student = analysis_input.get("student_answer")
        if not isinstance(question, dict) or not isinstance(student, dict):
            raise HTTPException(status_code=422, detail="OCR 未返回可用于判题的结构化题干和作答")
        question_text = str(question.get("text", "") or "").strip()
        student_answer = str(student.get("text", "") or "").strip()
        if not question_text:
            raise HTTPException(status_code=422, detail="未能可靠识别题目，请确保题干完整入镜且没有被手写内容遮挡")
        if not student_answer:
            raise HTTPException(status_code=422, detail="未能可靠识别学生最终作答，请确保答案清晰且未被涂改遮挡")
        if bool(analysis_input.get("review_required")):
            raise HTTPException(status_code=422, detail="OCR 结果需要人工确认，请重新拍摄题目和最终作答边界更清楚的照片")
        if ocr_data.get("status") == "low_confidence" or confidence < OCR_MIN_CONFIDENCE:
            confidence_percent = round(confidence * 100)
            raise HTTPException(
                status_code=422,
                detail=f"OCR 识别置信度不足（{confidence_percent}%），请重新上传清晰、完整的照片",
            )
    if not question_text:
        raise HTTPException(status_code=422, detail="判题需要题干或有效的 OCR 图片")
    allowed_question_ids = _batch_question_ids(request.batch_id)
    if request.question_id and allowed_question_ids is not None and request.question_id not in allowed_question_ids:
        raise HTTPException(status_code=422, detail="题目不属于当前作业批次")
    graph_question = fetch_question(request.question_id) if request.question_id else None
    question_id = str(graph_question.get("id", "") or "").strip() if graph_question else None
    standard_answer = str(graph_question.get("answer", "") or "").strip() if graph_question else None
    standard_solve_steps = graph_question.get("answer_steps") if graph_question else None
    if graph_question and (not question_id or not standard_answer):
        raise HTTPException(status_code=422, detail="知识图谱题目缺少可用于判题的标准答案")
    analysis_request = {
        "student_id": request.student_id,
        "question_id": question_id,
        "original_question": question_text,
        "student_write": student_answer,
        "standard_answer": standard_answer,
        "standard_solve_steps": standard_solve_steps,
    }
    if request.batch_id is not None:
        analysis_request["batch_id"] = request.batch_id
    if allowed_question_ids is not None:
        analysis_request["allowed_question_ids"] = allowed_question_ids
    return {
        "question_id": question_id,
        "knowledge_id": str(graph_question.get("knowledge_id", "") or "").strip() or None if graph_question else None,
        "ocr_data": ocr_data,
        "analysis_request": analysis_request,
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


def _scope_validation_fallback(request: SubmitRequest, analysis: dict[str, Any], question_id: str, ocr_data: dict[str, Any]) -> SubmitResponse:
    """Keep an unclassified teacher-uploaded question usable when inferred knowledge is out of scope.

    Teacher imports currently store the answer and grade but may not have a canonical
    knowledge-point mapping. Error analysis can infer a plausible point, but that
    inference must not turn a valid judgment into a gateway 422.
    """
    return SubmitResponse(
        status="success",
        data={
            "judge_result": analysis["judge_result"],
            "step_feedback": analysis["step_feedback"],
            "error_step_list": analysis.get("error_step_list", []),
            "miss_step_list": analysis.get("miss_step_list", []),
            "question_id": question_id,
            "question_source": analysis.get("question_source", "teacher_upload"),
            "question_pending_review": analysis.get("question_pending_review", False),
            "answer_released": False,
            "error_tags": [],
            "low_confidence": True,
            "next_action": "teacher_review",
            "warning": "题目尚未绑定适用知识点，已完成判题，暂跳过知识讲解。",
            **ocr_data,
        },
    )


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
        canonical_knowledge_id = prepared["knowledge_id"] or _lookup_knowledge_id(question_id)
        knowledge_id = analysis.get("knowledge_id") or canonical_knowledge_id
        if analysis["judge_result"] == "correct":
            if request.image and analysis.get("question_pending_review"):
                return SubmitResponse(status="success", data={
                    "judge_result": "correct",
                    "step_feedback": analysis["step_feedback"],
                    "original_question": analysis["original_question"],
                    "student_write": analysis["student_write"],
                    "question_id": question_id,
                    "question_source": analysis.get("question_source"),
                    "question_pending_review": True,
                    "answer_released": False,
                    "next_action": "teacher_review",
                    **ocr_data,
                })
            if not knowledge_id:
                return SubmitResponse(status="success", data={"judge_result": "correct", "step_feedback": analysis["step_feedback"], "master_level": 1.0, "next_action": "guide", "warning": "无法确定题目对应的知识点，跳过状态更新", **ocr_data})
            _ensure_question_knowledge_mapping(question_id, knowledge_id)
            state = execute_downstream("学习状态服务", lambda: update_state(request.student_id, knowledge_id, True, analysis["confidence"], analysis.get("answer_history_id")))
            state = require_fields("学习状态服务", state, {"master_level", "next_action", "knowledge_mastery_id", "should_generate_review"})
            review = None
            if state["should_generate_review"]:
                review = execute_downstream("复习计划服务", lambda: generate_review(request.student_id, knowledge_id, state["knowledge_mastery_id"], state["master_level"]))
                review = require_fields("复习计划服务", review, {"review_plan_id", "status"})
            return SubmitResponse(status="success", data={"judge_result": "correct", "step_feedback": analysis["step_feedback"], "knowledge_id": knowledge_id, "master_level": state["master_level"], "mastery": state.get("mastery"), "priority": state.get("priority"), "next_action": state["next_action"], "review_plan": review, **ocr_data})
        if request.image and analysis.get("question_pending_review"):
            mistake_case_id = _ensure_mistake_case(
                request.student_id,
                question_id,
                analysis.get("answer_history_id"),
            )
            return SubmitResponse(
                status="success",
                data={
                    "judge_result": analysis["judge_result"],
                    "step_feedback": analysis["step_feedback"],
                    "original_question": analysis["original_question"],
                    "student_write": analysis["student_write"],
                    "mistake_case_id": mistake_case_id,
                    "question_id": question_id,
                    "question_source": analysis.get("question_source"),
                    "question_pending_review": True,
                    "answer_released": False,
                    "error_tags": [],
                    "low_confidence": True,
                    "next_action": "teacher_review",
                    **ocr_data,
                },
            )
        error_analysis = execute_downstream("错因分析服务", lambda: analyze_error(_build_error_analysis_payload(analysis)))
        error_analysis = require_fields(
            "错因分析服务",
            error_analysis,
            {"error_tags", "knowledge_id", "knowledge_scope", "reasoning_content", "total_confidence", "low_confidence", "fallback_used"},
        )
        knowledge_id = error_analysis.get("knowledge_id") or knowledge_id
        if not knowledge_id:
            if not analysis.get("question_pending_review"):
                raise HTTPException(status_code=422, detail="错因分析未能确定知识点，无法继续生成教学内容")
            mistake_case_id = error_analysis.get("mistake_case_id") or _ensure_mistake_case(
                request.student_id,
                question_id,
                analysis.get("answer_history_id"),
            )
            return SubmitResponse(
                status="success",
                data={
                    "judge_result": analysis["judge_result"],
                    "step_feedback": analysis["step_feedback"],
                    "original_question": analysis["original_question"],
                    "student_write": analysis["student_write"],
                    "mistake_case_id": mistake_case_id,
                    "question_id": question_id,
                    "standard_answer": analysis.get("standard_answer"),
                    "standard_solve_steps": analysis.get("standard_solve_steps"),
                    "question_source": analysis.get("question_source"),
                    "question_pending_review": analysis.get("question_pending_review", False),
                    "answer_released": False,
                    "error_tags": [],
                    "low_confidence": True,
                    "next_action": "teacher_review",
                    **ocr_data,
                },
            )
        knowledge_payload = {
            "knowledge_id": knowledge_id,
            "knowledge_scope": error_analysis.get("knowledge_scope", ""),
            "grade": request.grade or "三年级",
        }
        try:
            knowledge = execute_downstream("知识服务", lambda: retrieve_knowledge(knowledge_payload))
        except HTTPException as error:
            # An inferred knowledge point is not authoritative for a question that
            # has no teacher/graph mapping. Preserve the judgment and route it for
            # teacher review instead of exposing an opaque 422 to students.
            detail = str(error.detail or "")
            if not canonical_knowledge_id and "out of syllabus" in detail.lower():
                return _scope_validation_fallback(request, analysis, question_id, ocr_data)
            raise
        knowledge = require_fields(
            "知识服务", knowledge, {"knowledge_explanation", "difficulty", "standard_solution", "common_errors", "teaching_tips"}
        )
        _ensure_question_knowledge_mapping(question_id, knowledge_id)
        frequency = execute_downstream("教学频控服务", lambda: check_frequency(request.student_id, knowledge_id))
        frequency = require_fields("教学频控服务", frequency, {"push_permission"})
        if not frequency["push_permission"]:
            state = execute_downstream("学习状态服务", lambda: update_state(request.student_id, knowledge_id, False, error_analysis["total_confidence"], analysis.get("answer_history_id"), error_analysis.get("mistake_case_id")))
            state = require_fields("学习状态服务", state, {"master_level", "knowledge_mastery_id", "should_generate_review"})
            review = None
            if state["should_generate_review"]:
                review = execute_downstream("复习计划服务", lambda: generate_review(request.student_id, knowledge_id, state["knowledge_mastery_id"], state["master_level"]))
                review = require_fields("复习计划服务", review, {"review_plan_id", "status"})
            return SubmitResponse(status="success", data={"judge_result": analysis["judge_result"], "step_feedback": analysis["step_feedback"], "error_tags": error_analysis["error_tags"], "knowledge_id": knowledge_id, "knowledge_scope": error_analysis["knowledge_scope"], "knowledge_explanation": knowledge["knowledge_explanation"], "master_level": state["master_level"], "mastery": state.get("mastery"), "priority": state.get("priority"), "next_action": "frequency_limit_exceeded", "frequency_info": frequency, "reasoning_content": error_analysis["reasoning_content"], "low_confidence": error_analysis["low_confidence"], "fallback_used": error_analysis["fallback_used"], "review_plan": review, **ocr_data})
        state = execute_downstream("学习状态服务", lambda: update_state(request.student_id, knowledge_id, False, error_analysis["total_confidence"], analysis.get("answer_history_id"), error_analysis.get("mistake_case_id")))
        state = require_fields("学习状态服务", state, {"master_level", "knowledge_mastery_id", "should_generate_review", "next_action", "correct_count", "wrong_count", "mastery_status"})
        teaching = execute_downstream("教学生成服务", lambda: generate_teaching(_build_teaching_payload(error_analysis, state["master_level"], analysis, request.grade or "三年级")))
        teaching = require_fields("教学生成服务", teaching, {"explanation", "hints", "practice_list", "teaching_mode", "fallback_used"})
        review = None
        if state["should_generate_review"]:
            review = execute_downstream("复习计划服务", lambda: generate_review(request.student_id, knowledge_id, state["knowledge_mastery_id"], state["master_level"]))
            review = require_fields("复习计划服务", review, {"review_plan_id", "status"})
        fallback_used = bool(error_analysis["fallback_used"] or teaching["fallback_used"])
        response_data = {"judge_result": analysis["judge_result"], "step_feedback": analysis["step_feedback"], "error_step_list": analysis["error_step_list"], "miss_step_list": analysis["miss_step_list"], "is_copy": analysis["is_copy"], "core_error_type": analysis["core_error_type"], "confidence": analysis["confidence"], "error_tags": error_analysis["error_tags"], "reasoning_content": error_analysis["reasoning_content"], "total_confidence": error_analysis["total_confidence"], "low_confidence": error_analysis["low_confidence"], "mistake_case_id": error_analysis.get("mistake_case_id"), "knowledge_id": knowledge_id, "knowledge_scope": error_analysis["knowledge_scope"], "knowledge_explanation": knowledge["knowledge_explanation"], "difficulty": knowledge["difficulty"], "standard_solution": knowledge["standard_solution"], "common_errors": knowledge["common_errors"], "teaching_tips": knowledge["teaching_tips"], "explanation": teaching["explanation"], "guided_explanation": teaching.get("guided_explanation", ""), "final_answer_explanation": teaching.get("final_answer_explanation", ""), "hints": teaching["hints"], "practice_list": teaching["practice_list"], "teaching_mode": teaching["teaching_mode"], "fallback_used": fallback_used, "error_analysis_fallback_used": error_analysis["fallback_used"], "teaching_fallback_used": teaching["fallback_used"], "fallback_reason": teaching.get("fallback_reason"), "practice_fallback_reason": teaching.get("practice_fallback_reason"), "master_level": state["master_level"], "mastery": state.get("mastery"), "priority": state.get("priority"), "mastery_components": state.get("mastery_components"), "priority_components": state.get("components"), "formula_version": state.get("formula_version"), "next_action": state["next_action"], "correct_count": state["correct_count"], "wrong_count": state["wrong_count"], "mastery_status": state["mastery_status"], "review_plan": review, "standard_answer": analysis.get("standard_answer"), "standard_solve_steps": analysis.get("standard_solve_steps"), "question_source": analysis.get("question_source"), "question_pending_review": analysis.get("question_pending_review", False), **ocr_data}
        response_data.update({
            "original_question": analysis["original_question"],
            "student_write": analysis["student_write"],
        })
        release_allowed = (
            _is_answer_released(question_id, request.batch_id)
            if request.batch_id
            else _is_answer_released(question_id)
        )
        if analysis.get("question_pending_review") or not release_allowed:
            for sensitive_key in (
                "answer", "answer_steps", "standard_answer", "standard_solve_steps",
                "standard_explanation", "final_answer_explanation", "explanation",
                "common_errors", "teaching_tips", "knowledge_explanation",
            ):
                response_data.pop(sensitive_key, None)
            response_data.update({"answer_released": False})
        else:
            response_data["answer_released"] = True
        return SubmitResponse(status="success", data=response_data)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail="提交编排发生未预期错误") from error
