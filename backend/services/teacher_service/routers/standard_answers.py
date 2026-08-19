from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services.teacher_service.standard_answer_service import upload_standard_answers


router = APIRouter(prefix="/internal/api/v1/teacher", tags=["teacher-standard-answers"])


@router.post("/standard_answers")
async def upload_standard_answer_image(image: UploadFile = File(...)) -> dict:
    content_type = image.content_type or ""
    if content_type not in {"image/jpeg", "image/png", "image/webp", "image/bmp"}:
        raise HTTPException(status_code=415, detail="仅支持 JPEG、PNG、WebP 和 BMP 图片。")
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="上传的标准答案图片为空。")
    return upload_standard_answers(image_bytes, image.filename or "standard-answer-image", content_type)
