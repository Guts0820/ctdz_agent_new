from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))


def test_gateway_turns_validated_ocr_output_into_a_standard_answer_judging_request(
    monkeypatch,
) -> None:
    from backend.api_gateway import app as api_gateway_app
    from backend.api_gateway.models import SubmitRequest
    from backend.api_gateway.services import submission_service

    ocr_data = {
        "confidence": 0.98,
        "status": "success",
        "analysis_input": {
            "question": {
                "text": "学校买了24箱矿泉水，每箱有3瓶，一共买了多少瓶？",
                "explanation": "求总瓶数",
                "visual_context": [],
            },
            "student_answer": {"text": "72"},
        },
    }
    monkeypatch.setattr(submission_service, "recognize_submission_image", lambda image: ocr_data)

    prepared = submission_service.prepare_judging_input(
        SubmitRequest(student_id="S-0001", image="data:image/png;base64,aW1hZ2U=")
    )

    assert api_gateway_app.title == "AI Math Error Correction System API Gateway"

    assert prepared["question_id"] is None
    assert prepared["knowledge_id"] is None
    assert prepared["ocr_data"] == ocr_data
    assert prepared["analysis_request"] == {
        "student_id": "S-0001",
        "question_id": None,
        "original_question": "学校买了24箱矿泉水，每箱有3瓶，一共买了多少瓶？",
        "student_write": "72",
        "standard_answer": None,
        "standard_solve_steps": None,
    }


def test_gateway_accepts_qwen_confidence_above_the_shared_080_threshold(monkeypatch) -> None:
    from backend.api_gateway.models import SubmitRequest
    from backend.api_gateway.services import submission_service

    monkeypatch.setattr(
        submission_service,
        "recognize_submission_image",
        lambda _image: {
            "confidence": 0.84,
            "status": "success",
            "analysis_input": {
                "question": {"text": "0.8×0.02=", "explanation": "计算", "visual_context": []},
                "student_answer": {"text": "0.016"},
                "review_required": False,
            },
        },
    )

    prepared = submission_service.prepare_judging_input(
        SubmitRequest(student_id="S-0001", image="data:image/png;base64,aW1hZ2U=")
    )

    assert prepared["analysis_request"]["student_write"] == "0.016"


def test_gateway_reports_missing_student_answer_instead_of_calling_it_blurry(monkeypatch) -> None:
    import pytest
    from fastapi import HTTPException
    from backend.api_gateway.models import SubmitRequest
    from backend.api_gateway.services import submission_service

    monkeypatch.setattr(
        submission_service,
        "recognize_submission_image",
        lambda _image: {
            "confidence": 0.99,
            "status": "low_confidence",
            "analysis_input": {
                "question": {"text": "1+17=", "explanation": "计算", "visual_context": []},
                "student_answer": {"text": ""},
                "review_required": True,
            },
        },
    )

    with pytest.raises(HTTPException, match="学生最终作答"):
        submission_service.prepare_judging_input(
            SubmitRequest(student_id="S-0001", image="data:image/png;base64,aW1hZ2U=")
        )
