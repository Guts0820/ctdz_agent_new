from fastapi import APIRouter, Query

from backend.services.teacher_service.question_bank_service import list_teacher_questions
from backend.services.teacher_service.models import TeacherQuestionListResponse


router = APIRouter(prefix="/internal/api/v1/teacher/questions", tags=["teacher-question-bank"])


@router.get("", response_model=TeacherQuestionListResponse)
def get_teacher_questions(
    teacher_id: str = Query(..., min_length=1),
    grade: int | None = Query(None, ge=1, le=6),
    semester: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
) -> TeacherQuestionListResponse:
    # teacher_id is deliberately an audit/context parameter; the bank is shared.
    return TeacherQuestionListResponse(**list_teacher_questions(
        grade=grade,
        semester=semester,
        page=page,
        page_size=page_size,
        keyword=keyword,
    ))
