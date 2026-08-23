"""Question retrieval orchestration for OCR-only submissions."""

import os
from typing import Any, Optional

import requests

from backend.services.analysis_service.llm_judge import rerank_question_candidates
from backend.shared.config import HTTP_TIMEOUT_SECONDS, KNOWLEDGE_GRAPH_URL


def _float_setting(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def retrieve_question_candidates(
    question_text: str,
    limit: int = 5,
    allowed_question_ids: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Retrieve lexical candidates from the graph-owned question index."""
    response = requests.get(
        f"{KNOWLEDGE_GRAPH_URL.rstrip('/')}/api/questions/candidates",
        params={"text": question_text, "limit": limit},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    candidates = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(candidates, list):
        raise ValueError("知识图谱候选题目响应格式错误")
    allowed = {str(item) for item in (allowed_question_ids or [])}
    return [
        candidate for candidate in candidates
        if isinstance(candidate, dict) and (not allowed or str(candidate.get("id")) in allowed)
    ]


def _build_match(candidate: dict[str, Any], rerank: dict[str, Any]) -> dict[str, Any]:
    return {
        "question": candidate,
        "question_id": str(candidate["id"]),
        "knowledge_id": candidate.get("knowledge_id"),
        "match_confidence": float(rerank["confidence"]),
        "match_reason": str(rerank.get("reason", "")),
    }


def resolve_question_reference(
    question_text: str,
    allowed_question_ids: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    """Resolve an OCR question only when the match is sufficiently reliable."""
    try:
        candidates = retrieve_question_candidates(question_text, allowed_question_ids=allowed_question_ids)
    except TypeError:
        # Keep compatibility with lightweight test/adapters that implement the
        # original one-argument retrieval contract.
        candidates = retrieve_question_candidates(question_text)
    if not candidates:
        return None

    try:
        rerank = rerank_question_candidates(question=question_text, candidates=candidates)
    except Exception:
        # A normalized exact match is safe without the external reranker. Fuzzy
        # candidates must not be guessed when the LLM is unavailable.
        exact = next(
            (candidate for candidate in candidates if candidate.get("match_type") == "normalized_exact"),
            None,
        )
        if exact is None:
            return None
        return _build_match(
            exact,
            {
                "confidence": 1.0,
                "reason": "题干规范化后完全匹配。",
            },
        )

    selected_id = rerank.get("question_id")
    if not selected_id:
        return None
    min_confidence = _float_setting("ANALYSIS_QUESTION_MATCH_MIN_CONFIDENCE", 0.90)
    min_margin = _float_setting("ANALYSIS_QUESTION_MATCH_MIN_MARGIN", 0.10)
    confidence = float(rerank.get("confidence", 0.0))
    runner_up_confidence = float(rerank.get("runner_up_confidence", 0.0))
    if confidence < min_confidence or confidence - runner_up_confidence < min_margin:
        return None

    selected = next((candidate for candidate in candidates if candidate.get("id") == selected_id), None)
    if selected is None:
        return None
    return _build_match(selected, rerank)
