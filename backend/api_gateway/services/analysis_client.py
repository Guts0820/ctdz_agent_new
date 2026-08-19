"""判题服务客户端。"""

from typing import Any

import requests
from fastapi import HTTPException

from backend.api_gateway.services.service_urls import SERVICE_URLS


def analyze_submission(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{SERVICE_URLS['analysis']}/internal/api/v1/analysis/process",
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = {}
        detail = body.get("detail") if isinstance(body, dict) else None
        raise HTTPException(
            status_code=response.status_code,
            detail=detail or f"判题服务返回 HTTP {response.status_code}",
        )
    return response.json()
