import json

from app.schemas import validate_judging_input


def test_allows_an_empty_question_when_annotations_make_the_stem_unreliable() -> None:
    payload = {
        "schema_version": "1.0",
        "question": {"text": "", "explanation": "", "visual_context": []},
        "student_answer": {"text": ""},
        "confidence": 0.2,
        "review_required": True,
    }

    assert validate_judging_input(json.dumps(payload, ensure_ascii=False)) == payload


def test_ignores_schema_metadata_echoed_at_the_response_root() -> None:
    payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"VisualContext": {"type": "object"}},
        "schema_version": "1.0",
        "question": {"text": "1+1=", "explanation": "求和。", "visual_context": []},
        "student_answer": {"text": "2"},
        "confidence": 0.99,
        "review_required": False,
    }

    result = validate_judging_input(json.dumps(payload, ensure_ascii=False))

    assert result["question"]["text"] == "1+1="
    assert "$defs" not in result
