from typing import Any

import requests
from fastapi import HTTPException

from backend.api_gateway.services.service_urls import SERVICE_URLS


def upload_standard_answer_image(image_bytes: bytes, filename: str, content_type: str) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{SERVICE_URLS['teacher']}/internal/api/v1/teacher/standard_answers",
            files={"image": (filename, image_bytes, content_type)},
            timeout=660,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"教师端服务不可用：{error}") from error
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        raise HTTPException(
            status_code=response.status_code,
            detail=detail or f"教师端服务返回 HTTP {response.status_code}",
        )
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="教师端服务返回了无效 JSON。")
    return payload
