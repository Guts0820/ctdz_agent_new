import requests

from backend.api_gateway.services.gateway_database import get_gateway_db
from backend.api_gateway.services.service_urls import SERVICE_URLS


def get_mastery(student_id: str) -> dict:
    response = requests.get(f"{SERVICE_URLS['state']}/internal/api/v1/state/mastery/{student_id}", timeout=10)
    response.raise_for_status()
    return response.json()


def get_class_mistake_stats(class_name: str) -> dict:
    with get_gateway_db() as connection:
        rows = connection.execute(
            """SELECT qkm.knowledge_id, COUNT(*) AS error_count,
                      GROUP_CONCAT(DISTINCT ah.core_error_type) AS error_types
               FROM answer_history ah
               JOIN question_knowledge_mapping qkm ON ah.question_id = qkm.question_id
               WHERE ah.is_correct = 0
               GROUP BY qkm.knowledge_id ORDER BY error_count DESC LIMIT 5"""
        ).fetchall()
    return {"class_name": class_name, "data": [{"knowledge_id": row["knowledge_id"], "error_count": row["error_count"], "error_types": (row["error_types"] or "").split(",")} for row in rows]}


def get_student_stats(student_id: str) -> dict:
    with get_gateway_db() as connection:
        total = connection.execute("SELECT COUNT(*) AS total FROM answer_history WHERE student_id = ?", (student_id,)).fetchone()["total"]
        correct = connection.execute("SELECT COUNT(*) AS total FROM answer_history WHERE student_id = ? AND is_correct = 1", (student_id,)).fetchone()["total"]
        wrong = connection.execute(
            "SELECT COUNT(*) AS total FROM mistake_case WHERE student_id = ?",
            (student_id,),
        ).fetchone()["total"]
        reviewed = connection.execute(
            "SELECT COUNT(*) AS total FROM mistake_case WHERE student_id = ? AND current_status = 'corrected'",
            (student_id,),
        ).fetchone()["total"]
    return {"total_questions": total, "correct_rate": round(correct / total * 100) if total else 0, "total_mistakes": wrong, "reviewed_mistakes": reviewed}


def get_wrong_answers(student_id: str) -> dict:
    with get_gateway_db() as connection:
        rows = connection.execute(
            """SELECT mc.mistake_case_id, mc.question_id, mc.current_status, mc.created_at,
                      initial.student_ocr_answer, initial.core_error_type, initial.ocr_question,
                      q.question_description,
                      (SELECT COUNT(*) FROM answer_history attempts
                       WHERE attempts.mistake_case_id = mc.mistake_case_id
                         AND attempts.submit_type = '错题订正') AS correction_count,
                      (SELECT latest.student_ocr_answer FROM answer_history latest
                       WHERE latest.mistake_case_id = mc.mistake_case_id
                         AND latest.submit_type = '错题订正'
                       ORDER BY latest.submitted_at DESC LIMIT 1) AS correction_answer,
                      (SELECT latest.submitted_at FROM answer_history latest
                       WHERE latest.mistake_case_id = mc.mistake_case_id
                         AND latest.submit_type = '错题订正'
                       ORDER BY latest.submitted_at DESC LIMIT 1) AS corrected_at
               FROM mistake_case mc
               LEFT JOIN answer_history initial ON initial.answer_history_id = (
                   SELECT ah.answer_history_id FROM answer_history ah
                   WHERE ah.mistake_case_id = mc.mistake_case_id
                   ORDER BY ah.submitted_at LIMIT 1
               )
               LEFT JOIN question q ON mc.question_id = q.question_id
               WHERE mc.student_id = ? ORDER BY mc.created_at DESC""",
            (student_id,),
        ).fetchall()
    data = [{
        "id": row["mistake_case_id"], "mistake_case_id": row["mistake_case_id"],
        "question_id": row["question_id"],
        "question_text": row["ocr_question"] or row["question_description"] or row["question_id"] or "",
        "student_answer": row["student_ocr_answer"] or "",
        "correction_answer": row["correction_answer"] or "",
        "error_type": row["core_error_type"] or "未知",
        "date": row["corrected_at"] or row["created_at"] or "",
        "last_wrong_time": row["created_at"] or "",
        "status": row["current_status"], "reviewed": row["current_status"] == "corrected",
        "wrong_count": 1, "correction_count": row["correction_count"],
    } for row in rows]
    return {"student_id": student_id, "total": len(data), "data": data}
