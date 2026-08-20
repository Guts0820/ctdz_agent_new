from fastapi import APIRouter

from backend.services.review_service.review.dependencies import priority_service
from backend.services.review_service.review.schemas.priority import MasteryUpdateRequest, MasteryUpdateResponse, PriorityRunRequest, PriorityRunResponse


router = APIRouter(prefix="/priority-runs", tags=["Priority"])


@router.post("", response_model=PriorityRunResponse)
def calculate_priority(request: PriorityRunRequest) -> PriorityRunResponse:
    return priority_service.run_for_student(request.student_id, request.business_date)


@router.post("/internal/mastery-update", response_model=MasteryUpdateResponse, include_in_schema=False)
def update_mastery(request: MasteryUpdateRequest) -> MasteryUpdateResponse:
    return priority_service.update_mastery(request)
