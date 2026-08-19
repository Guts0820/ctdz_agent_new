from typing import Any

import requests
from fastapi import HTTPException

from backend.shared.config import (
    KNOWLEDGE_GRAPH_URL,
    OCR_MIN_CONFIDENCE,
    OCR_SERVICE_URL,
    OCR_TIMEOUT_SECONDS,
)


def build_graph_items(ocr_payload: dict[str, Any]) -> list[dict[str, str]]:
    """Extract only question text, explanation, and standard answer for Neo4j."""
    analysis_input = ocr_payload.get("analysis_input", ocr_payload)
    if not isinstance(analysis_input, dict):
        raise HTTPException(status_code=422, detail="OCR 未返回标准答案结构。")

    confidence = float(analysis_input.get("confidence", ocr_payload.get("confidence", 0)))
    review_required = bool(analysis_input.get("review_required", ocr_payload.get("review_required", False)))
    if review_required or confidence < OCR_MIN_CONFIDENCE:
        raise HTTPException(status_code=422, detail="标准答案图片识别置信度不足，请重新上传。")

    raw_questions = analysis_input.get("questions")
    if not isinstance(raw_questions, list):
        single_question = analysis_input.get("question")
        single_answer = analysis_input.get("student_answer")
        if isinstance(single_question, dict) and isinstance(single_answer, dict):
            raw_questions = [{"question": single_question, "student_answer": single_answer}]
    if not isinstance(raw_questions, list) or not raw_questions:
        raise HTTPException(status_code=422, detail="OCR 未识别到可分离的标准答案题目。")

    items: list[dict[str, str]] = []
    for raw_question in raw_questions:
        if not isinstance(raw_question, dict):
            continue
        question = raw_question.get("question")
        answer = raw_question.get("student_answer")
        if not isinstance(question, dict) or not isinstance(answer, dict):
            continue
        text = str(question.get("text", "")).strip()
        explanation = str(question.get("explanation", "")).strip()
        standard_answer = str(answer.get("text", "")).strip()
        if text and standard_answer:
            items.append({"text": text, "explanation": explanation, "answer": standard_answer})

    if not items:
        raise HTTPException(status_code=422, detail="OCR 未返回完整的题干和标准答案。")
    return items


def _raise_downstream_error(response: requests.Response, service_name: str) -> None:
    if response.status_code < 400:
        return
    try:
        body = response.json()
    except ValueError:
        body = {}
    detail = body.get("detail") if isinstance(body, dict) else None
    raise HTTPException(
        status_code=502,
        detail=detail or f"{service_name}返回 HTTP {response.status_code}",
    )


def upload_standard_answers(image_bytes: bytes, filename: str, content_type: str) -> dict[str, Any]:
    """Run standard-answer OCR and persist the validated fields through the graph service."""
    try:
        ocr_response = requests.post(
            f"{OCR_SERVICE_URL.rstrip('/')}/v1/recognize",
            files={"image": (filename, image_bytes, content_type)},
            data={"mode": "standard_answer"},
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"OCR 服务不可用：{error}") from error
    _raise_downstream_error(ocr_response, "OCR 服务")
    try:
        ocr_payload = ocr_response.json()
    except ValueError as error:
        raise HTTPException(status_code=502, detail="OCR 服务返回了无效 JSON。") from error

    graph_items = build_graph_items(ocr_payload)
    try:
        graph_response = requests.post(
            f"{KNOWLEDGE_GRAPH_URL.rstrip('/')}/internal/api/questions/standard-answer",
            json={"items": graph_items},
            timeout=30,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail=f"知识图谱服务不可用：{error}") from error
    _raise_downstream_error(graph_response, "知识图谱服务")
    try:
        graph_payload = graph_response.json()
    except ValueError as error:
        raise HTTPException(status_code=502, detail="知识图谱服务返回了无效 JSON。") from error

    return {
        "status": "success",
        "imported_count": graph_payload.get("imported_count", len(graph_items)),
        "questions": graph_payload.get("questions", []),
        "ocr": {
            "confidence": ocr_payload.get("confidence"),
            "engine": ocr_payload.get("engine"),
            "status": ocr_payload.get("status"),
        },
    }
