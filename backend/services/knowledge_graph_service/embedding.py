"""Qwen Embedding client used by the knowledge-graph vector index."""

import os
from typing import Any

from openai import OpenAI

from backend.shared.http_client import create_direct_httpx_client
from backend.shared.config import (
    QWEN_EMBEDDING_API_KEY,
    QWEN_EMBEDDING_BASE_URL,
    QWEN_EMBEDDING_DIMENSIONS,
    QWEN_EMBEDDING_MODEL,
    QWEN_EMBEDDING_TIMEOUT_SECONDS,
)


class EmbeddingNotConfigured(RuntimeError):
    """Raised when no Qwen embedding API key is configured."""


class QwenEmbeddingClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("QWEN_EMBEDDING_API_KEY") or os.getenv("QWEN_API_KEY") or QWEN_EMBEDDING_API_KEY
        self.base_url = (
            os.getenv("QWEN_EMBEDDING_BASE_URL")
            or os.getenv("QWEN_BASE_URL")
            or QWEN_EMBEDDING_BASE_URL
        ).rstrip("/")
        self.model = os.getenv("QWEN_EMBEDDING_MODEL") or QWEN_EMBEDDING_MODEL
        self.dimensions = int(os.getenv("QWEN_EMBEDDING_DIMENSIONS", str(QWEN_EMBEDDING_DIMENSIONS)))
        self.timeout = float(
            os.getenv("QWEN_EMBEDDING_TIMEOUT_SECONDS", str(QWEN_EMBEDDING_TIMEOUT_SECONDS))
        )
        self._client: Any | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def _get_client(self) -> Any:
        if not self.is_configured:
            raise EmbeddingNotConfigured("Qwen embedding API key is not configured.")
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                http_client=create_direct_httpx_client(),
            )
        return self._client

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._get_client().embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]


def build_question_embedding_text(question: dict[str, Any]) -> str:
    parts = [str(question.get("text", "")).strip()]
    aliases = question.get("aliases") or []
    if aliases:
        parts.append("；".join(str(alias).strip() for alias in aliases if str(alias).strip()))
    explanation = str(question.get("explanation", "")).strip()
    if explanation:
        parts.append(explanation)
    return "\n".join(part for part in parts if part)


def embed_questions(questions: list[dict[str, Any]]) -> list[list[float] | None]:
    client = QwenEmbeddingClient()
    if not client.is_configured:
        return [None for _ in questions]
    texts = [build_question_embedding_text(question) for question in questions]
    return list(client.embed_texts(texts))


def embed_query_text(text: str) -> list[float] | None:
    client = QwenEmbeddingClient()
    if not client.is_configured:
        return None
    return client.embed_texts([text])[0]
