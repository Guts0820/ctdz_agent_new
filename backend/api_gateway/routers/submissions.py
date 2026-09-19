from fastapi import APIRouter, Header

from backend.api_gateway.models import SubmitRequest, SubmitResponse
from backend.api_gateway.services.submission_service import process_submission


router = APIRouter(tags=["submissions"])


@router.post("/api/v1/submit", response_model=SubmitResponse)
def submit_homework(
    request: SubmitRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> SubmitResponse:
    return process_submission(request, request_id=x_request_id)
