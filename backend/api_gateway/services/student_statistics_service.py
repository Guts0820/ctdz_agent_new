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
        wrong = connection.execute("SELECT COUNT(*) AS total FROM answer_history WHERE student_id = ? AND is_correct = 0", (student_id,)).fetchone()["total"]
        reviewed = connection.execute("SELECT COUNT(*) AS total FROM review2_attempt WHERE student_answer IS NOT NULL AND correction_is_correct IS NOT NULL").fetchone()["total"]
    return {"total_questions": total, "correct_rate": round(correct / total * 100) if total else 0, "total_mistakes": wrong, "reviewed_mistakes": reviewed}


def get_wrong_answers(student_id: str) -> dict:
    with get_gateway_db() as connection:
        rows = connection.execute(
            """SELECT ah.answer_history_id, ah.question_id, ah.student_ocr_answer, ah.core_error_type,
                      ah.submitted_at, q.question_description
               FROM answer_history ah LEFT JOIN question q ON ah.question_id = q.question_id
               WHERE ah.student_id = ? AND ah.is_correct = 0 ORDER BY ah.submitted_at DESC""",
            (student_id,),
        ).fetchall()
    data = [{"id": row["answer_history_id"], "question_id": row["question_id"], "question_text": row["question_description"] or row["question_id"] or "", "student_answer": row["student_ocr_answer"] or "", "error_type": row["core_error_type"] or "未知", "date": row["submitted_at"] or "", "reviewed": False, "wrong_count": 1} for row in rows]
    return {"student_id": student_id, "total": len(data), "data": data}
