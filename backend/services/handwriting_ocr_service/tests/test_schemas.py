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
