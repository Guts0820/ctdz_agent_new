from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from backend.api_gateway.services.teacher_question_import_client import (
    confirm_teacher_question_import,
    preview_teacher_question_import,
)


router = APIRouter(prefix="/api/v1/teacher/question-imports", tags=["teacher-question-imports"])


class ConfirmImportRequest(BaseModel):
    teacher_id: str = Field(min_length=1)
    items: list[dict] = Field(min_length=1)


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


@router.post("/{import_id}/confirm")
async def confirm_question_import(import_id: str, request: ConfirmImportRequest) -> dict:
    return confirm_teacher_question_import(import_id, request.model_dump())
