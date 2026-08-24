from fastapi import APIRouter, Query

from backend.api_gateway.services.teacher_question_bank_client import list_teacher_questions


router = APIRouter(prefix="/api/v1/teacher/questions", tags=["teacher-question-bank"])


@router.get("")
def get_teacher_questions(
    teacher_id: str = Query(..., min_length=1),
    grade: int | None = Query(None, ge=1, le=6),
    semester: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
) -> dict:
    return list_teacher_questions(
        teacher_id=teacher_id,
        grade=grade,
        semester=semester,
        page=page,
        page_size=page_size,
        keyword=keyword,
    )
