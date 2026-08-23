from datetime import datetime
from typing import Any

import requests

from fastapi import HTTPException

from backend.shared.id_utils import generate_id
from backend.services.teacher_service.database import get_teacher_db
from backend.services.teacher_service.models import BatchResponse, BatchListResponse, CreateBatchRequest
from backend.shared.config import KNOWLEDGE_GRAPH_URL, HTTP_TIMEOUT_SECONDS


def _validate_ready_questions(question_ids: list[str]) -> list[str]:
    """Ensure every selected canonical question is ready before assignment."""
    unique_ids = list(dict.fromkeys(str(question_id).strip() for question_id in question_ids if str(question_id).strip()))
    if not unique_ids:
        raise HTTPException(status_code=422, detail="作业批次至少需要一道题目")
    for question_id in unique_ids:
        try:
            response = requests.get(
                f"{KNOWLEDGE_GRAPH_URL.rstrip('/')}/api/questions/{question_id}",
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            raise HTTPException(status_code=503, detail="统一题库服务暂不可用，请稍后重试") from error
        if response.status_code == 404:
            raise HTTPException(status_code=422, detail=f"题目 {question_id} 不在统一题库中")
        if response.status_code >= 400:
            raise HTTPException(status_code=503, detail="统一题库题目状态暂不可用，请稍后重试")
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as error:
            raise HTTPException(status_code=503, detail="统一题库返回了无效题目状态") from error
        status = str(payload.get("status") or "ready").lower()
        solution_status = str(payload.get("standard_solution_status") or "ready").lower()
        if status != "ready" or solution_status != "ready":
            raise HTTPException(status_code=422, detail=f"题目 {question_id} 尚未完成标准解题，不能布置")
    return unique_ids


def create_batch(request: CreateBatchRequest) -> BatchResponse:
    batch_id = generate_id("HB")
    question_ids = _validate_ready_questions(request.question_ids)
    with get_teacher_db() as connection:
        connection.execute(
            """INSERT INTO homework_batch
            (batch_id, class_id, teacher_id, batch_date, release_status, created_at)
            VALUES (?, ?, ?, ?, 'locked', ?)""",
            (batch_id, request.class_id, request.teacher_id, request.batch_date, datetime.now().isoformat()),
        )
        connection.executemany(
            "INSERT INTO homework_batch_question (batch_id, question_id) VALUES (?, ?)",
            [(batch_id, question_id) for question_id in question_ids],
        )
        connection.commit()
    return BatchResponse(
        batch_id=batch_id,
        class_id=request.class_id,
        teacher_id=request.teacher_id,
        batch_date=request.batch_date,
        release_status="locked",
        question_count=len(question_ids),
        question_ids=question_ids,
    )


def list_batches(teacher_id: str | None = None, class_id: str | None = None) -> BatchListResponse:
    with get_teacher_db() as connection:
        clauses, params = [], []
        if teacher_id:
            clauses.append("hb.teacher_id = ?")
            params.append(teacher_id)
        if class_id:
            clauses.append("hb.class_id = ?")
            params.append(class_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = connection.execute(
            f"SELECT hb.batch_id, hb.class_id, hb.teacher_id, hb.batch_date, hb.release_status, "
            f"COUNT(hbq.question_id) AS question_count FROM homework_batch hb "
            f"LEFT JOIN homework_batch_question hbq ON hbq.batch_id = hb.batch_id{where} "
            "GROUP BY hb.batch_id ORDER BY hb.created_at DESC", params
        ).fetchall()
        result = []
        for row in rows:
            ids = [item[0] for item in connection.execute(
                "SELECT question_id FROM homework_batch_question WHERE batch_id = ? ORDER BY rowid", (row["batch_id"],)
            ).fetchall()]
            result.append(BatchResponse(**dict(row), question_ids=ids))
    return BatchListResponse(data=result, total=len(result))


def release_batch(batch_id: str) -> dict:
    with get_teacher_db() as connection:
        if not connection.execute(
            "SELECT 1 FROM homework_batch WHERE batch_id = ?", (batch_id,)
        ).fetchone():
            raise HTTPException(status_code=404, detail=f"批次不存在: {batch_id}")
        connection.execute(
            "UPDATE homework_batch SET release_status = 'released', release_time = ? "
            "WHERE batch_id = ?",
            (datetime.now().isoformat(), batch_id),
        )
        connection.commit()
    return {"status": "success", "message": f"批次 {batch_id} 已全部放行", "release_status": "released"}


def release_partial_batch(batch_id: str, question_ids: list[str]) -> dict:
    with get_teacher_db() as connection:
        if not connection.execute(
            "SELECT 1 FROM homework_batch WHERE batch_id = ?", (batch_id,)
        ).fetchone():
            raise HTTPException(status_code=404, detail=f"批次不存在: {batch_id}")
        requested = list(dict.fromkeys(str(question_id).strip() for question_id in question_ids if str(question_id).strip()))
        assigned = {row[0] for row in connection.execute(
            "SELECT question_id FROM homework_batch_question WHERE batch_id = ?", (batch_id,)
        ).fetchall()}
        invalid = [question_id for question_id in requested if question_id not in assigned]
        if invalid:
            raise HTTPException(status_code=422, detail=f"题目不属于当前批次: {', '.join(invalid)}")
        if not requested:
            raise HTTPException(status_code=422, detail="精细放行至少需要选择一道当前批次题目")
        timestamp = datetime.now().isoformat()
        connection.executemany(
            "INSERT OR IGNORE INTO question_release_override "
            "(batch_id, question_id, released_at) VALUES (?, ?, ?)",
            [(batch_id, question_id, timestamp) for question_id in requested],
        )
        connection.execute(
            "UPDATE homework_batch SET release_status = 'partial', release_time = ? "
            "WHERE batch_id = ?",
            (timestamp, batch_id),
        )
        connection.commit()
    return {
        "status": "success",
        "message": f"已放行 {len(requested)} 道题目",
        "release_status": "partial",
        "released_count": len(requested),
    }
