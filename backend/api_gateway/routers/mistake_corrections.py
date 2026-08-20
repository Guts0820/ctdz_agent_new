from fastapi import APIRouter

from backend.api_gateway.models import MistakeCorrectionRequest, MistakeCorrectionResponse
from backend.api_gateway.services.mistake_correction_service import process_mistake_correction


router = APIRouter(tags=["mistake-corrections"])


@router.post(
    "/api/v1/mistakes/{mistake_case_id}/correction",
    response_model=MistakeCorrectionResponse,
)
def submit_mistake_correction(
    mistake_case_id: str,
    request: MistakeCorrectionRequest,
) -> MistakeCorrectionResponse:
    return process_mistake_correction(mistake_case_id, request)
