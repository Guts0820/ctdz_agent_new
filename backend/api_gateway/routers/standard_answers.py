from fastapi import APIRouter, File, UploadFile

from backend.api_gateway.services.teacher_standard_answer_client import upload_standard_answer_image


router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-standard-answers"])


@router.post("/standard_answers")
async def upload_teacher_standard_answers(image: UploadFile = File(...)) -> dict:
    return upload_standard_answer_image(
        await image.read(),
        image.filename or "standard-answer-image",
        image.content_type or "application/octet-stream",
    )
