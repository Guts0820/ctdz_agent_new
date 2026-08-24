"""Read-only teacher view of the shared, assignable question bank."""

from typing import Any

import requests
from fastapi import HTTPException

from backend.shared.config import HTTP_TIMEOUT_SECONDS, KNOWLEDGE_GRAPH_URL


def list_teacher_questions(
    *,
    grade: int | None,
    semester: str | None,
    page: int,
    page_size: int,
    keyword: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"page": 1, "page_size": 100}
    if grade is not None:
        params["grade"] = grade
    if semester:
        params["semester"] = semester
    try:
        response = requests.get(
            f"{KNOWLEDGE_GRAPH_URL.rstrip('/')}/api/questions",
            params=params,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail="统一题库服务暂不可用，请稍后重试") from error
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail="统一题库查询失败，请稍后重试")
    try:
        payload = response.json()
    except ValueError as error:
        raise HTTPException(status_code=503, detail="统一题库返回了无效题目列表") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise HTTPException(status_code=503, detail="统一题库返回了无效题目列表")

    needle = (keyword or "").strip().casefold()
    ready_questions = []
    for question in payload["data"]:
        if not isinstance(question, dict):
            continue
        status = str(question.get("status") or "ready").lower()
        solution_status = str(question.get("standard_solution_status") or "ready").lower()
        if status != "ready" or solution_status != "ready":
            continue
        if needle and needle not in str(question.get("text") or "").casefold():
            continue
        ready_questions.append(question)

    start = (page - 1) * page_size
    return {
        "data": ready_questions[start : start + page_size],
        "total": len(ready_questions),
        "page": page,
        "page_size": page_size,
    }
