from datetime import datetime

from fastapi import HTTPException

from backend.shared.id_utils import generate_id
from backend.services.teacher_service.database import get_teacher_db
from backend.services.teacher_service.models import BatchResponse, CreateBatchRequest


def create_batch(request: CreateBatchRequest) -> BatchResponse:
    batch_id = generate_id("HB")
    with get_teacher_db() as connection:
        connection.execute(
            """INSERT INTO homework_batch
            (batch_id, class_id, teacher_id, batch_date, release_status, created_at)
            VALUES (?, ?, ?, ?, 'locked', ?)""",
            (batch_id, request.class_id, request.teacher_id, request.batch_date, datetime.now().isoformat()),
        )
        connection.executemany(
            "INSERT INTO homework_batch_question (batch_id, question_id) VALUES (?, ?)",
            [(batch_id, question_id) for question_id in request.question_ids],
        )
        connection.commit()
    return BatchResponse(
        batch_id=batch_id,
        class_id=request.class_id,
        teacher_id=request.teacher_id,
        batch_date=request.batch_date,
        release_status="locked",
        question_count=len(request.question_ids),
    )


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
        timestamp = datetime.now().isoformat()
        connection.executemany(
            "INSERT OR IGNORE INTO question_release_override "
            "(batch_id, question_id, released_at) VALUES (?, ?, ?)",
            [(batch_id, question_id, timestamp) for question_id in question_ids],
        )
        connection.execute(
            "UPDATE homework_batch SET release_status = 'partial', release_time = ? "
            "WHERE batch_id = ?",
            (timestamp, batch_id),
        )
        connection.commit()
    return {
        "status": "success",
        "message": f"已放行 {len(question_ids)} 道题目",
        "release_status": "partial",
        "released_count": len(question_ids),
    }
