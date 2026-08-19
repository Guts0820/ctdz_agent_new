from fastapi import APIRouter

from backend.api_gateway.models import BatchResponse, CreateBatchRequest, ReleasePartialRequest
from backend.api_gateway.services.teacher_client import (
    create_batch,
    release_batch,
    release_partial_batch,
)


router = APIRouter(prefix="/api/v1/teacher/homework_batch", tags=["homework-batches"])


@router.post("", response_model=BatchResponse)
def create_homework_batch(request: CreateBatchRequest) -> BatchResponse:
    return BatchResponse(**create_batch(request.model_dump()))


@router.post("/{batch_id}/release")
def release_homework_batch(batch_id: str) -> dict:
    return release_batch(batch_id)


@router.post("/{batch_id}/release_partial")
def release_partial_homework_batch(batch_id: str, request: ReleasePartialRequest) -> dict:
    return release_partial_batch(batch_id, request.question_ids)

