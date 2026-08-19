from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_teacher_service_exposes_standard_answer_upload_route() -> None:
    from backend.services.teacher_service.main import app

    assert "/internal/api/v1/teacher/standard_answers" in app.openapi()["paths"]


def test_standard_answer_items_map_to_graph_fields() -> None:
    from backend.services.teacher_service.standard_answer_service import build_graph_items

    payload = {
        "schema_version": "1.0",
        "questions": [
            {
                "question": {"text": "1+1=", "explanation": "计算和。", "visual_context": []},
                "student_answer": {"text": "2"},
            }
        ],
        "confidence": 0.99,
        "review_required": False,
    }

    items = build_graph_items(payload)

    assert items == [{"text": "1+1=", "explanation": "计算和。", "answer": "2"}]


def test_single_question_ocr_result_is_accepted_for_standard_answer_upload() -> None:
    from backend.services.teacher_service.standard_answer_service import build_graph_items

    payload = {
        "analysis_input": {
            "schema_version": "1.0",
            "question": {"text": "Q0088题干", "explanation": "按图判断。", "visual_context": []},
            "student_answer": {"text": "2，1，3"},
            "confidence": 0.98,
            "review_required": False,
        }
    }

    assert build_graph_items(payload) == [
        {"text": "Q0088题干", "explanation": "按图判断。", "answer": "2，1，3"}
    ]


def test_gateway_exposes_public_standard_answer_upload_route() -> None:
    from backend.api_gateway.app import app

    assert "/api/v1/teacher/standard_answers" in app.openapi()["paths"]


def test_knowledge_graph_exposes_internal_standard_answer_write_route() -> None:
    from backend.services.knowledge_graph_service.main import app

    assert "/internal/api/questions/standard-answer" in app.openapi()["paths"]
