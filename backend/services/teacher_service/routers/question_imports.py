from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.services.teacher_service.models import QuestionImportPreviewResponse
from backend.services.teacher_service.question_import_service import create_question_import_preview


router = APIRouter(prefix="/internal/api/v1/teacher/question-imports", tags=["teacher-question-imports"])
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}


@router.post("/preview", response_model=QuestionImportPreviewResponse)
async def preview_question_import(
    image: UploadFile = File(...),
    teacher_id: str = Form(...),
    grade: int = Form(...),
    semester: str | None = Form(None),
) -> QuestionImportPreviewResponse:
    content_type = image.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="仅支持 JPEG、PNG、WebP 和 BMP 图片。")
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="上传的标准答案图片为空。")
    return await run_in_threadpool(
        create_question_import_preview,
        image_bytes=image_bytes,
        filename=image.filename or "standard-answer-image",
        content_type=content_type,
        teacher_id=teacher_id,
        grade=grade,
        semester=semester,
    )
