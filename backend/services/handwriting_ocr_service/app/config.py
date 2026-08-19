import os
from dataclasses import dataclass


os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"


LOCAL_RUNTIME_ENVIRONMENT = "development"
PRODUCTION_RUNTIME_ENVIRONMENT = "production"
SUPPORTED_RUNTIME_ENVIRONMENTS = {
    LOCAL_RUNTIME_ENVIRONMENT,
    PRODUCTION_RUNTIME_ENVIRONMENT,
}


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    runtime_environment: str
    ocr_engine: str
    paddleocr_vl_device: str
    paddleocr_vl_pipeline_version: str
    confidence_threshold: float
    max_image_bytes: int
    qwen_fallback_enabled: bool
    qwen_api_key: str | None
    qwen_base_url: str | None
    qwen_model: str
    qwen_timeout_seconds: float
    qwen_fallback_confidence: float

    @classmethod
    def from_env(cls) -> "Settings":
        runtime_environment = os.getenv(
            "OCR_RUNTIME_ENV", LOCAL_RUNTIME_ENVIRONMENT
        ).strip().lower()
        if runtime_environment not in SUPPORTED_RUNTIME_ENVIRONMENTS:
            supported = ", ".join(sorted(SUPPORTED_RUNTIME_ENVIRONMENTS))
            raise ValueError(
                f"OCR_RUNTIME_ENV must be one of: {supported}."
            )

        pipeline_version = os.getenv(
            "PADDLEOCR_VL_PIPELINE_VERSION", "v1.6"
        ).strip()
        if pipeline_version not in {"v1", "v1.5", "v1.6"}:
            raise ValueError(
                "PADDLEOCR_VL_PIPELINE_VERSION must be 'v1', 'v1.5', or 'v1.6'."
            )

        default_device = (
            "gpu"
            if runtime_environment == PRODUCTION_RUNTIME_ENVIRONMENT
            else "cpu"
        )
        ocr_engine = os.getenv("OCR_ENGINE", "qwen").strip().lower()
        if ocr_engine not in {"qwen", "paddleocr_vl"}:
            raise ValueError("OCR_ENGINE must be 'qwen' or 'paddleocr_vl'.")
        return cls(
            runtime_environment=runtime_environment,
            ocr_engine=ocr_engine,
            paddleocr_vl_device=os.getenv(
                "PADDLEOCR_VL_DEVICE", default_device
            ).strip().lower(),
            paddleocr_vl_pipeline_version=pipeline_version,
            confidence_threshold=float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.80")),
            max_image_bytes=int(os.getenv("MAX_IMAGE_BYTES", str(10 * 1024 * 1024))),
            qwen_fallback_enabled=_as_bool(os.getenv("QWEN_VISION_FALLBACK_ENABLED")),
            qwen_api_key=os.getenv("QWEN_API_KEY"),
            qwen_base_url=os.getenv(
                "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
            qwen_model=os.getenv("QWEN_MODEL", "qwen-3.7plus"),
            qwen_timeout_seconds=float(os.getenv("QWEN_TIMEOUT_SECONDS", "30")),
            qwen_fallback_confidence=float(os.getenv("QWEN_FALLBACK_CONFIDENCE", "0.85")),
        )

    @property
    def qwen_is_configured(self) -> bool:
        return bool(
            self.qwen_api_key and self.qwen_base_url and self.qwen_model
        )
