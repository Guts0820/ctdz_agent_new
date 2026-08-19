from fastapi import APIRouter

from backend.api_gateway.models import ExternalErrorAnalyzeRequest
from backend.api_gateway.services.external_error_analysis_service import analyze_external_error


router = APIRouter(tags=["external-error-analysis"])


@router.post("/api/error/analyze")
def external_error_analyze(request: ExternalErrorAnalyzeRequest) -> dict:
    return analyze_external_error(request)
