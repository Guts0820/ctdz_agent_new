import os


def test_parent_growth_report_requires_elevated_role(monkeypatch):
    from fastapi import HTTPException
    from backend.api_gateway.routers.growth_report import parent_growth_report

    with __import__('pytest').raises(HTTPException) as error:
        parent_growth_report(1, "student")
    assert error.value.status_code == 403


def test_privileged_growth_report_routes_proxy_the_unified_contract(monkeypatch):
    from backend.api_gateway.routers import growth_report

    calls = []
    monkeypatch.setattr(
        growth_report,
        "proxy_review_request",
        lambda method, prefix, path, body: calls.append((method, prefix, path, body)) or {"source": "growth_report_v1"},
    )

    assert growth_report.parent_growth_report("S001", "parent") == {"source": "growth_report_v1"}
    assert growth_report.admin_growth_report("S001", "admin") == {"source": "growth_report_v1"}
    assert calls == [
        ("GET", "api/datahub", "growth_report/S001", None),
        ("GET", "api/datahub", "growth_report/S001", None),
    ]

    with __import__('pytest').raises(__import__('fastapi').HTTPException) as error:
        growth_report.admin_growth_report("S001", "parent")
    assert error.value.status_code == 403


def test_error_tags_have_stable_practice_mapping():
    from backend.services.teaching_service.main import ErrorTag, map_error_tags_to_practice

    result = map_error_tags_to_practice([ErrorTag(error_id="E1", level1="计算", level2="乘法", level3="进位错误")])
    assert result == {"E1": "knowledge:乘法|skill:进位错误"}


def test_priority_mastery_weights_are_configurable(monkeypatch):
    from backend.services.review_service.review.services.priority_calculator import PriorityCalculator
    from backend.services.review_service.review.schemas.priority import KnowledgeStateInput
    from datetime import date, datetime

    monkeypatch.setenv("MASTERY_WEIGHT_ACCURACY", "1")
    monkeypatch.setenv("MASTERY_WEIGHT_CONSISTENCY", "0")
    monkeypatch.setenv("MASTERY_WEIGHT_RETENTION", "0")
    monkeypatch.setenv("MASTERY_WEIGHT_ERROR_CONTROL", "0")
    state = KnowledgeStateInput(student_id="S1", knowledge_point_id="K1", correct_count=1, wrong_count=0, correct_streak=1, wrong_streak=0, evidence=[])
    result = PriorityCalculator().calculate(state, date.today(), datetime.now())
    assert 0 <= result.mastery.mastery <= 100


def test_ocr_result_exposes_visual_complexity_metadata():
    from backend.services.handwriting_ocr_service.app.models import RecognitionResult

    payload = RecognitionResult(markdown="x", confidence=1, engine="test", fallback_used=False, status="success", question_count=2, visual_block_count=1, complexity="complex_visual").as_dict()
    assert payload["question_count"] == 2
    assert payload["complexity"] == "complex_visual"
