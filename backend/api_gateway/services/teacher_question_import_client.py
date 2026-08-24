from typing import Any

import requests
from fastapi import HTTPException

from backend.api_gateway.services.service_urls import SERVICE_URLS


def _response_payload(response: requests.Response) -> dict[str, Any]:
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


def preview_teacher_question_import(
    *,
    image_bytes: bytes,
    filename: str,
    content_type: str,
    teacher_id: str,
    grade: int,
    semester: str | None,
) -> dict[str, Any]:
    data: dict[str, str] = {"teacher_id": teacher_id, "grade": str(grade)}
    if semester:
        data["semester"] = semester
    try:
        response = requests.post(
            f"{SERVICE_URLS['teacher']}/internal/api/v1/teacher/question-imports/preview",
            files={"image": (filename, image_bytes, content_type)},
            data=data,
            timeout=660,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"教师端服务不可用：{error}") from error
    return _response_payload(response)


def confirm_teacher_question_import(import_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{SERVICE_URLS['teacher']}/internal/api/v1/teacher/question-imports/{import_id}/confirm",
            json=payload,
            timeout=60,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"教师端服务不可用：{error}") from error
    return _response_payload(response)
