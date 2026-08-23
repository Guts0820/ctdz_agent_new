"""教师端业务服务客户端。"""

from typing import Any

import requests
from fastapi import HTTPException

from backend.api_gateway.services.service_urls import SERVICE_URLS


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = requests.request(
            method,
            f"{SERVICE_URLS['teacher']}{path}",
            json=payload,
            timeout=10,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"教师端服务不可用：{error}") from error

    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = {}
        detail = body.get("detail") if isinstance(body, dict) else None
        raise HTTPException(
            status_code=response.status_code,
            detail=detail or f"教师端服务返回 HTTP {response.status_code}",
        )
    try:
        return response.json()
    except ValueError as error:
        raise HTTPException(status_code=502, detail="教师端服务返回了无效 JSON") from error


def create_batch(payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", "/internal/api/v1/teacher/homework_batch", payload)


def release_batch(batch_id: str) -> dict[str, Any]:
    return _request("POST", f"/internal/api/v1/teacher/homework_batch/{batch_id}/release")


def release_partial_batch(batch_id: str, question_ids: list[str]) -> dict[str, Any]:
    return _request(
        "POST",
        f"/internal/api/v1/teacher/homework_batch/{batch_id}/release_partial",
        {"question_ids": question_ids},
    )


def list_batches(teacher_id: str | None = None, class_id: str | None = None) -> dict[str, Any]:
    params = []
    if teacher_id:
        params.append(f"teacher_id={teacher_id}")
    if class_id:
        params.append(f"class_id={class_id}")
    path = "/internal/api/v1/teacher/homework_batch" + ("?" + "&".join(params) if params else "")
    return _request("GET", path)


def list_batch_submissions(batch_id: str) -> dict[str, Any]:
    return _request("GET", f"/internal/api/v1/teacher/homework_batch/{batch_id}/submissions")


def review_batch_submission(batch_id: str, answer_history_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", f"/internal/api/v1/teacher/homework_batch/{batch_id}/submissions/{answer_history_id}/review", payload)
