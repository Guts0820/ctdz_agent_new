from fastapi import APIRouter, HTTPException, Query
from backend.api_gateway.services.gateway_database import get_gateway_db

from backend.api_gateway.models import BatchResponse, CreateBatchRequest, ReleasePartialRequest
from backend.api_gateway.services.teacher_client import (
    create_batch,
    release_batch,
    release_partial_batch,
    list_batches,
    list_student_batches,
    list_batch_submissions,
    review_batch_submission,
)


router = APIRouter(prefix="/api/v1/teacher/homework_batch", tags=["homework-batches"])


@router.post("", response_model=BatchResponse)
def create_homework_batch(request: CreateBatchRequest) -> BatchResponse:
    return BatchResponse(**create_batch(request.model_dump()))


@router.get("")
def get_homework_batches(teacher_id: str | None = Query(None), class_id: str | None = Query(None)):
    return list_batches(teacher_id=teacher_id, class_id=class_id)


@router.get("/student/{student_id}/homework_batches")
def get_student_homework_batches(student_id: str):
    with get_gateway_db() as connection:
        row = connection.execute("SELECT student_class FROM students WHERE student_id = ?", (student_id,)).fetchone()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="未找到学生班级信息")
    return list_student_batches(str(row[0]))


@router.post("/{batch_id}/release")
def release_homework_batch(batch_id: str) -> dict:
    return release_batch(batch_id)


@router.post("/{batch_id}/release_partial")
def release_partial_homework_batch(batch_id: str, request: ReleasePartialRequest) -> dict:
    return release_partial_batch(batch_id, request.question_ids)


@router.get("/{batch_id}/submissions")
def get_batch_submissions(batch_id: str):
    return list_batch_submissions(batch_id)


@router.post("/{batch_id}/submissions/{answer_history_id}/review")
def review_submission(batch_id: str, answer_history_id: str, payload: dict):
    return review_batch_submission(batch_id, answer_history_id, payload)

