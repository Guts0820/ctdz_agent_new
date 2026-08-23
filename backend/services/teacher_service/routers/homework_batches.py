from fastapi import APIRouter, Query

from backend.services.teacher_service.homework_batch_service import (
    create_batch,
    release_batch,
    release_partial_batch,
    list_batches,
    list_batch_submissions,
    review_submission,
)
from backend.services.teacher_service.models import (
    BatchResponse,
    BatchListResponse,
    CreateBatchRequest,
    ReleasePartialRequest,
    ManualReviewRequest,
)


router = APIRouter(prefix="/internal/api/v1/teacher/homework_batch", tags=["teacher"])


@router.post("", response_model=BatchResponse)
def create_homework_batch(request: CreateBatchRequest) -> BatchResponse:
    return create_batch(request)


@router.get("", response_model=BatchListResponse)
def get_homework_batches(teacher_id: str | None = Query(None), class_id: str | None = Query(None)) -> BatchListResponse:
    return list_batches(teacher_id=teacher_id, class_id=class_id)


@router.post("/{batch_id}/release")
def release_homework_batch(batch_id: str) -> dict:
    return release_batch(batch_id)


@router.post("/{batch_id}/release_partial")
def release_homework_batch_partial(batch_id: str, request: ReleasePartialRequest) -> dict:
    return release_partial_batch(batch_id, request.question_ids)


@router.get("/{batch_id}/submissions")
def get_batch_submissions(batch_id: str) -> dict:
    return list_batch_submissions(batch_id)


@router.post("/{batch_id}/submissions/{answer_history_id}/review")
def manual_review_submission(batch_id: str, answer_history_id: str, request: ManualReviewRequest) -> dict:
    return review_submission(batch_id, answer_history_id, request)
