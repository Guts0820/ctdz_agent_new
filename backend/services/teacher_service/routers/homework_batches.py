from fastapi import APIRouter

from backend.services.teacher_service.homework_batch_service import (
    create_batch,
    release_batch,
    release_partial_batch,
)
from backend.services.teacher_service.models import (
    BatchResponse,
    CreateBatchRequest,
    ReleasePartialRequest,
)


router = APIRouter(prefix="/internal/api/v1/teacher/homework_batch", tags=["teacher"])


@router.post("", response_model=BatchResponse)
def create_homework_batch(request: CreateBatchRequest) -> BatchResponse:
    return create_batch(request)


@router.post("/{batch_id}/release")
def release_homework_batch(batch_id: str) -> dict:
    return release_batch(batch_id)


@router.post("/{batch_id}/release_partial")
def release_homework_batch_partial(batch_id: str, request: ReleasePartialRequest) -> dict:
    return release_partial_batch(batch_id, request.question_ids)
