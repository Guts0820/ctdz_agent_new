from fastapi import APIRouter

from backend.api_gateway.models import SubmitRequest, SubmitResponse
from backend.api_gateway.services.submission_service import process_submission


router = APIRouter(tags=["submissions"])


@router.post("/api/v1/submit", response_model=SubmitResponse)
def submit_homework(request: SubmitRequest) -> SubmitResponse:
    return process_submission(request)
