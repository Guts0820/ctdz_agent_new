"""知识讲解服务客户端。"""

from typing import Any

import requests

from backend.api_gateway.services.service_urls import SERVICE_URLS


def retrieve_knowledge(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{SERVICE_URLS['knowledge']}/internal/api/v1/knowledge/retrieve",
        json={**payload, "textbook_version": "人教版"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
