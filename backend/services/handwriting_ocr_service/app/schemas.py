"""Stable, validated OCR output contract for the downstream judging service."""

import json
from typing import Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VisualContext(SchemaModel):
    kind: Literal["diagram", "table", "chart", "image", "other"]
    description: str = Field(min_length=1)


class QuestionContent(SchemaModel):
    text: str
    explanation: str
    visual_context: list[VisualContext] = Field(default_factory=list)


class StudentAnswer(SchemaModel):
    text: str = ""


class JudgingInput(SchemaModel):
    schema_version: Literal["1.0"] = "1.0"
    question: QuestionContent
    student_answer: StudentAnswer
    confidence: float = Field(ge=0, le=1)
    review_required: bool


class StandardAnswerQuestion(SchemaModel):
    question: QuestionContent
    student_answer: StudentAnswer


class StandardAnswerInput(SchemaModel):
    schema_version: Literal["1.0"] = "1.0"
    questions: list[StandardAnswerQuestion] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    review_required: bool


JUDGING_INPUT_JSON_SCHEMA = JudgingInput.model_json_schema()
_validator = Draft202012Validator(JUDGING_INPUT_JSON_SCHEMA)
STANDARD_ANSWER_INPUT_JSON_SCHEMA = StandardAnswerInput.model_json_schema()
_standard_answer_validator = Draft202012Validator(STANDARD_ANSWER_INPUT_JSON_SCHEMA)


def validate_judging_input(content: str) -> dict[str, object]:
    """Parse and validate Qwen content against the published JSON Schema."""
    normalized = content.strip()
    if normalized.startswith("```json"):
        normalized = normalized[7:]
    if normalized.startswith("```"):
        normalized = normalized[3:]
    if normalized.endswith("```"):
        normalized = normalized[:-3]

    try:
        payload = _normalize_model_payload(json.loads(normalized.strip()), required_key="question")
    except json.JSONDecodeError as error:
        raise ValueError("Qwen OCR output is not valid JSON.") from error

    errors = sorted(_validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        raise ValueError(f"Qwen OCR output failed JSON Schema validation: {errors[0].message}")
    try:
        return JudgingInput.model_validate(payload).model_dump(mode="json")
    except ValidationError as error:
        raise ValueError("Qwen OCR output failed JSON Schema validation.") from error


def validate_standard_answer_input(content: str) -> dict[str, object]:
    """Parse and validate OCR output containing one or more standard answers."""
    normalized = content.strip()
    if normalized.startswith("```json"):
        normalized = normalized[7:]
    if normalized.startswith("```"):
        normalized = normalized[3:]
    if normalized.endswith("```"):
        normalized = normalized[:-3]

    try:
        payload = _normalize_model_payload(json.loads(normalized.strip()), required_key="questions")
    except json.JSONDecodeError as error:
        raise ValueError("Qwen OCR standard-answer output is not valid JSON.") from error

    errors = sorted(_standard_answer_validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        raise ValueError(
            f"Qwen OCR standard-answer output failed JSON Schema validation: {errors[0].message}"
        )
    try:
        return StandardAnswerInput.model_validate(payload).model_dump(mode="json")
    except ValidationError as error:
        raise ValueError("Qwen OCR standard-answer output failed JSON Schema validation.") from error


def _normalize_model_payload(payload: object, *, required_key: str) -> object:
    """Remove schema metadata occasionally echoed by multimodal models.

    The model is shown a JSON Schema in the prompt. Some successful responses
    echo root-level ``$defs``/``$schema`` metadata alongside the actual result.
    Those metadata keys are not part of the response contract, so discard them
    only when the expected result key is present; all normal field validation
    remains strict below.
    """
    if not isinstance(payload, dict) or required_key not in payload:
        return payload
    return {
        key: value
        for key, value in payload.items()
        if key not in {"$defs", "$schema"}
    }
