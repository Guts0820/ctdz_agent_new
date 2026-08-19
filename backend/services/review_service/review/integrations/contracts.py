from typing import Protocol

from backend.services.review_service.review.schemas.priority import KnowledgeStateInput


class KnowledgeStateClient(Protocol):
    def get_states(self, student_id: str) -> list[KnowledgeStateInput]: ...
    def apply_attempt_evidence(self, event: dict) -> None: ...


class AIGradingClient(Protocol):
    def request_grading(self, attempt: dict) -> str: ...


class KnowledgeGraphClient(Protocol):
    def get_question_mapping(self, question_id: str) -> list[dict]: ...
