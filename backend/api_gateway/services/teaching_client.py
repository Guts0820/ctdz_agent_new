"""教学建议和频率控制服务客户端。"""

from datetime import datetime
from typing import Any

import requests

from backend.api_gateway.services.service_urls import SERVICE_URLS


def generate_teaching(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{SERVICE_URLS['teaching']}/internal/api/v1/teaching/generate",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def check_frequency(student_id: str, knowledge_id: str) -> dict[str, Any]:
    response = requests.post(
        f"{SERVICE_URLS['teaching']}/internal/api/v1/teaching/frequency-check",
        json={"student_id": student_id, "knowledge_id": knowledge_id, "current_time": datetime.now().isoformat()},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
