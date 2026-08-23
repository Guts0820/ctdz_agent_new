from typing import Any

import requests
from fastapi import HTTPException

from backend.api_gateway.services.service_urls import SERVICE_URLS


def request_admin_questions(method: str, path: str, payload: dict[str, Any] | None = None, role: str | None = None, actor: str | None = None) -> dict[str, Any]:
    try:
        response = requests.request(
            method,
            f"{SERVICE_URLS['knowledge_graph']}{path}",
            json=payload,
            headers={"X-Role": role or "", "X-Actor": actor or ""},
            timeout=15,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"题库管理服务不可用：{error}") from error
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=body.get("detail", "题库管理请求失败"))
    return body
