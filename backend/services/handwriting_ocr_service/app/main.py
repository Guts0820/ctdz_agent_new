import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functools import lru_cache

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from dotenv import load_dotenv
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.models import RecognitionResult
from app.services.paddleocr_vl import PaddleOCRVLEngine
from app.services.qwen_vision import QwenVisionEngine
from app.services.recognition_service import RecognitionService

SERVICE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_service_environment() -> None:
    """Load OCR credentials only from this service's environment file."""
    load_dotenv(os.path.join(SERVICE_ROOT, ".env"))


load_service_environment()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
settings = Settings.from_env()


@lru_cache
def build_recognition_service() -> RecognitionService:
    if settings.ocr_engine == "qwen":
        primary_engine = QwenVisionEngine(settings)
        fallback_engine = None
    else:
        primary_engine = PaddleOCRVLEngine(
            device=settings.paddleocr_vl_device,
            pipeline_version=settings.paddleocr_vl_pipeline_version,
        )
        fallback_engine = QwenVisionEngine(settings) if settings.qwen_is_configured else None
    return RecognitionService(
        primary_engine=primary_engine,
        fallback_engine=fallback_engine,
        confidence_threshold=settings.confidence_threshold,
    )


def _recognize_image(image_bytes: bytes, content_type: str, mode: str = "student_work") -> RecognitionResult:
    """Initialize the cached model and run inference in the worker thread."""
    service = build_recognition_service()
    if mode == "student_work":
        return service.recognize(image_bytes, content_type)
    return service.recognize(image_bytes, content_type, mode=mode)


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Handwriting OCR Service", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/v1/recognize")
async def recognize_handwriting(
    image: UploadFile = File(...),
    mode: str = Form("student_work"),
) -> dict[str, object]:
    mode = mode if isinstance(mode, str) else "student_work"
    if mode not in {"student_work", "standard_answer"}:
        raise HTTPException(status_code=422, detail="Unsupported OCR mode.")
    content_type = image.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, WebP, and BMP images are supported.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(image_bytes) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="The uploaded image exceeds the configured size limit.")

    try:
        result = await run_in_threadpool(
            _recognize_image,
            image_bytes,
            content_type,
            mode,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Image recognition failed: {error}") from error

    return result.as_dict()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8089)
