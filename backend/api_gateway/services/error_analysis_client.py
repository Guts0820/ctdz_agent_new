"""错因分析服务客户端。"""

from typing import Any

import requests

from backend.api_gateway.services.service_urls import SERVICE_URLS


def analyze_error(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{SERVICE_URLS['error_analysis']}/internal/api/v1/error-analysis/analyze",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
