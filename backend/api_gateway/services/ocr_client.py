"""OCR 服务客户端。"""

import base64
import io
from typing import Any

import requests
from fastapi import HTTPException

from backend.shared.config import OCR_SERVICE_URL, OCR_TIMEOUT_SECONDS


def _decode_submission_image(image: str) -> tuple[bytes, str]:
    if image.startswith("data:"):
        header, _, encoded_image = image.partition(",")
        content_type = header.split(";")[0].replace("data:", "") or "image/png"
    else:
        content_type = "image/png"
        encoded_image = image
    try:
        return base64.b64decode(encoded_image), content_type
    except ValueError as error:
        raise HTTPException(status_code=422, detail="图片不是有效的 Base64 数据") from error


def recognize_submission_image(image: str) -> dict[str, Any]:
    """将前端图片提交给独立 OCR 服务。"""
    image_bytes, content_type = _decode_submission_image(image)
    response = requests.post(
        f"{OCR_SERVICE_URL.rstrip('/')}/v1/recognize",
        files={"image": ("image", io.BytesIO(image_bytes), content_type)},
        timeout=OCR_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
