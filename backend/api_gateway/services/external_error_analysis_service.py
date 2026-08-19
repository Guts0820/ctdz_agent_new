import requests
from fastapi import HTTPException

from backend.api_gateway.models import ExternalErrorAnalyzeRequest
from backend.api_gateway.services.gateway_database import get_gateway_db
from backend.api_gateway.services.service_urls import SERVICE_URLS


def _fetch_question(question_id: str) -> dict:
    try:
        response = requests.get(f"{SERVICE_URLS['knowledge_graph']}/api/questions/{question_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        with get_gateway_db() as connection:
            row = connection.execute(
                """SELECT q.question_id, q.question_description, q.standard_solve_steps, q.answer,
                          q.difficulty, q.grade, qk.knowledge_id
                   FROM question q LEFT JOIN question_knowledge_mapping qk ON q.question_id = qk.question_id
                   WHERE q.question_id = ?""",
                (question_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")
        return {"id": row["question_id"], "text": row["question_description"] or "", "answer_steps": row["standard_solve_steps"] or "", "answer": row["answer"] or "", "difficulty": row["difficulty"] or "medium", "grade": row["grade"] or "三年级", "knowledge_id": row["knowledge_id"] or ""}


def analyze_external_error(request: ExternalErrorAnalyzeRequest) -> dict:
    try:
        question = _fetch_question(request.question_id)
    except HTTPException as error:
        return {"error": "question_not_found", "message": str(error.detail), "question_id": request.question_id}
    payload = {"student_id": f"U-{request.student_id}", "original_question": question.get("text", ""), "standard_solve_steps": question.get("answer_steps", ""), "correct_answer": request.correct_answer, "student_write": request.student_answer, "knowledge_id": question.get("knowledge_id", "")}
    try:
        response = requests.post(f"{SERVICE_URLS['error_analysis']}/internal/api/v1/error-analysis/analyze-light", json=payload, timeout=30)
        response.raise_for_status()
        analysis = response.json()
    except requests.RequestException as error:
        return {"error": "analysis_service_unavailable", "message": f"错因分析服务暂时不可用: {error}", "question_id": request.question_id}
    error_tags = analysis.get("error_tags", [])
    primary = error_tags[0] if error_tags else {}
    return {"error_type": primary.get("error_id", "unknown"), "error_type_label": primary.get("level3", "未知"), "error_detail": analysis.get("reasoning_content", ""), "related_knowledge": [analysis["knowledge_scope"]] if analysis.get("knowledge_scope") else [], "confidence": analysis.get("total_confidence", 0.0), "all_error_tags": [{"error_id": tag.get("error_id"), "level1": tag.get("level1"), "level2": tag.get("level2"), "level3": tag.get("level3"), "confidence": tag.get("confidence")} for tag in error_tags], "knowledge_id": analysis.get("knowledge_id", ""), "source": "light_analysis", "note": "本接口为轻量分析模式，仅基于最终答案推断，置信度相对保守"}
