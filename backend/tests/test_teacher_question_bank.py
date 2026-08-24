from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def test_teacher_question_bank_filters_ready_and_keyword(monkeypatch):
    from backend.services.teacher_service import question_bank_service

    captured = {}

    def fake_get(url, *, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "data": [
                    {"id": "Q1", "text": "0.8×0.02=", "status": "ready", "standard_solution_status": "ready"},
                    {"id": "Q2", "text": "未完成题", "status": "draft", "standard_solution_status": "ready"},
                    {"id": "Q3", "text": "别的题", "status": "ready", "standard_solution_status": "pending"},
                ],
                "total": 3,
            },
        )

    monkeypatch.setattr(question_bank_service.requests, "get", fake_get)
    result = question_bank_service.list_teacher_questions(
        grade=3, semester="上学期", page=1, page_size=20, keyword="0.8"
    )

    assert [item["id"] for item in result["data"]] == ["Q1"]
    assert result["total"] == 1
    assert captured["params"]["grade"] == 3


def test_teacher_question_bank_surfaces_downstream_failure(monkeypatch):
    from backend.services.teacher_service import question_bank_service

    def fake_get(*args, **kwargs):
        raise question_bank_service.requests.RequestException("offline")

    monkeypatch.setattr(question_bank_service.requests, "get", fake_get)
    with pytest.raises(HTTPException) as error:
        question_bank_service.list_teacher_questions(
            grade=None, semester=None, page=1, page_size=20, keyword=None
        )
    assert error.value.status_code == 503
    assert "不可用" in str(error.value.detail)


def test_gateway_teacher_question_route_is_exposed():
    from backend.api_gateway.app import app

    assert "/api/v1/teacher/questions" in app.openapi()["paths"]


def test_teacher_question_bank_client_encodes_query_values(monkeypatch):
    from backend.api_gateway.services import teacher_question_bank_client

    captured = {}

    def fake_request(method, path, payload=None):
        captured.update(method=method, path=path, payload=payload)
        return {"data": [], "total": 0, "page": 1, "page_size": 20}

    monkeypatch.setattr(teacher_question_bank_client, "_request", fake_request)
    teacher_question_bank_client.list_teacher_questions(
        teacher_id="T 001", grade=3, semester="上学期&下学期", page=1, page_size=20, keyword="0.8×"
    )
    assert "teacher_id=T+001" in captured["path"]
    assert "%26" in captured["path"]
    assert "%C3%97" in captured["path"]
