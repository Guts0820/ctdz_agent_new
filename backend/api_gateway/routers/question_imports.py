from fastapi import APIRouter, File, Form, UploadFile

from backend.api_gateway.services.teacher_question_import_client import preview_teacher_question_import


router = APIRouter(prefix="/api/v1/teacher/question-imports", tags=["teacher-question-imports"])


@router.post("/preview")
async def preview_question_import(
    image: UploadFile = File(...),
    teacher_id: str = Form(...),
    grade: int = Form(...),
    semester: str | None = Form(None),
) -> dict:
    return preview_teacher_question_import(
        image_bytes=await image.read(),
        filename=image.filename or "standard-answer-image",
        content_type=image.content_type or "application/octet-stream",
        teacher_id=teacher_id,
        grade=grade,
        semester=semester,
    )
