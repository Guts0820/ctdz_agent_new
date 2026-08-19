"""学习状态与复习计划服务客户端。"""

from typing import Any

import requests

from backend.api_gateway.services.service_urls import SERVICE_URLS


def update_state(student_id: str, knowledge_id: str, is_correct: bool, confidence: float) -> dict[str, Any]:
    response = requests.post(
        f"{SERVICE_URLS['state']}/internal/api/v1/state/update",
        json={"student_id": student_id, "knowledge_id": knowledge_id, "is_correct": is_correct, "confidence": confidence},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def generate_review(student_id: str, knowledge_id: str, mastery_id: str, master_level: float) -> dict[str, Any]:
    response = requests.post(
        f"{SERVICE_URLS['state']}/internal/api/v1/state/generate-review",
        json={"student_id": student_id, "knowledge_id": knowledge_id, "knowledge_mastery_id": mastery_id, "master_level": master_level},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
