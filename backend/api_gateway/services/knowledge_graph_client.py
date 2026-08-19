"""知识图谱服务客户端，图谱拥有题目和标准答案。"""

from typing import Any

import requests
from fastapi import HTTPException

from backend.api_gateway.services.service_urls import SERVICE_URLS


def fetch_question(question_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{SERVICE_URLS['knowledge_graph']}/api/questions/{question_id}", timeout=10
    )
    if response.status_code == 404:
        raise HTTPException(status_code=422, detail="知识图谱中不存在该题目的标准答案")
    response.raise_for_status()
    return response.json()


def resolve_question(question_text: str) -> dict[str, Any]:
    response = requests.get(
        f"{SERVICE_URLS['knowledge_graph']}/api/questions/resolve",
        params={"text": question_text},
        timeout=10,
    )
    if response.status_code == 404:
        raise HTTPException(status_code=422, detail="OCR 题干无法匹配知识图谱中的标准题目")
    response.raise_for_status()
    return response.json()
