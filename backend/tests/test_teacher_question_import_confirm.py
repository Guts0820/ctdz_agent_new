import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException


def _seed_import(database, db_path, *, status="review_required", expires_at=None) -> None:
    database.DATABASE_PATH = str(db_path)
    database.ensure_question_import_tables()
    now = datetime.now(timezone.utc)
    with database.get_teacher_db() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS question (
                question_id TEXT PRIMARY KEY, question_description TEXT, question_type TEXT,
                difficulty TEXT, grade TEXT, textbook_version TEXT,
                standard_solve_steps TEXT, answer TEXT
            )"""
        )
        connection.execute(
            "INSERT INTO teacher_question_import "
            "(import_id, teacher_id, grade, semester, status, image_sha256, request_key, created_at, expires_at) "
            "VALUES ('TQI-1', 'T001', 3, '上学期', ?, 'image-hash', 'request-key', ?, ?)",
            (
                status,
                now.isoformat(),
                (expires_at or now + timedelta(hours=1)).isoformat(),
            ),
        )
        connection.executemany(
            "INSERT INTO teacher_question_import_item "
            "(item_id, import_id, position, question_text, teacher_answer, teacher_explanation, "
            "llm_answer, llm_solve_steps, llm_difficulty, solution_source, comparison_status, "
            "comparison_reason, comparison_confidence, existing_question_id, created_at) "
            "VALUES (?, 'TQI-1', ?, ?, ?, ?, ?, ?, 'easy', ?, ?, '', 1, ?, ?)",
            [
                (
                    "ITEM-1",
                    1,
                    "0.8×0.02=",
                    "0.016",
                    "",
                    "0.016",
                    json.dumps(["8×2=16", "确定小数点位置"], ensure_ascii=False),
                    "llm",
                    "agreed",
                    None,
                    now.isoformat(),
                ),
                (
                    "ITEM-2",
                    2,
                    "6×7=",
                    "42",
                    "乘法口诀",
                    "42",
                    json.dumps(["六七四十二"], ensure_ascii=False),
                    "existing",
                    "agreed",
                    "Q42",
                    now.isoformat(),
                ),
            ],
        )
        connection.commit()


def _confirm_request():
    from backend.services.teacher_service.models import QuestionImportConfirmRequest

    return QuestionImportConfirmRequest.model_validate({
        "teacher_id": "T001",
        "items": [
            {
                "item_id": "ITEM-1",
                "decision": "teacher",
                "question_text": "0.8 × 0.02 =",
                "teacher_answer": "0.016",
            },
            {"item_id": "ITEM-2", "decision": "existing"},
        ],
    })


def test_confirm_route_is_exposed_by_teacher_service_and_gateway() -> None:
    from backend.api_gateway.app import app as gateway_app
    from backend.services.teacher_service.main import app as teacher_app

    path = "/api/v1/teacher/question-imports/{import_id}/confirm"
    assert f"/internal{path}" in teacher_app.openapi()["paths"]
    assert path in gateway_app.openapi()["paths"]


def test_confirm_persists_teacher_decision_and_reuses_existing_question(tmp_path, monkeypatch) -> None:
    from backend.services.teacher_service import database, question_import_service

    db_path = tmp_path / "confirm.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    _seed_import(database, db_path)
    captured = {}

    def upsert(items):
        captured["items"] = items
        return {items[0]["request_id"]: {"question_id": "QNEW", "result": "created"}}

    monkeypatch.setattr(question_import_service, "upsert_confirmed_questions", upsert)

    result = question_import_service.confirm_question_import("TQI-1", _confirm_request())

    assert result.status == "confirmed"
    assert [(item.item_id, item.question_id, item.result) for item in result.items] == [
        ("ITEM-1", "QNEW", "created"),
        ("ITEM-2", "Q42", "existing"),
    ]
    assert captured["items"][0]["grade"] == 3
    assert captured["items"][0]["semester"] == "上学期"
    assert captured["items"][0]["answer_source"] == "teacher"
    assert captured["items"][0]["status"] == "ready"
    assert captured["items"][0]["standard_solution_status"] == "ready"
    assert captured["items"][0]["created_by"] == "T001"
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT status FROM teacher_question_import WHERE import_id='TQI-1'"
        ).fetchone()[0] == "confirmed"
        assert connection.execute(
            "SELECT decision, confirmed_question_id FROM teacher_question_import_item WHERE item_id='ITEM-1'"
        ).fetchone() == ("teacher", "QNEW")
        assert connection.execute(
            "SELECT question_description, answer, grade FROM question WHERE question_id='QNEW'"
        ).fetchone() == ("0.8 × 0.02 =", "0.016", "3年级")


def test_confirm_rejects_non_owner_without_writing(tmp_path, monkeypatch) -> None:
    from backend.services.teacher_service import database, question_import_service

    db_path = tmp_path / "ownership.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    _seed_import(database, db_path)
    request = _confirm_request().model_copy(update={"teacher_id": "T999"})
    monkeypatch.setattr(
        question_import_service,
        "upsert_confirmed_questions",
        lambda _items: (_ for _ in ()).throw(AssertionError("must not write")),
    )

    with pytest.raises(HTTPException) as error:
        question_import_service.confirm_question_import("TQI-1", request)

    assert error.value.status_code == 403


def test_confirm_marks_expired_session_and_rejects_it(tmp_path, monkeypatch) -> None:
    from backend.services.teacher_service import database, question_import_service

    db_path = tmp_path / "expired.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    _seed_import(
        database,
        db_path,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    monkeypatch.setattr(
        question_import_service,
        "upsert_confirmed_questions",
        lambda _items: (_ for _ in ()).throw(AssertionError("must not write")),
    )

    with pytest.raises(HTTPException) as error:
        question_import_service.confirm_question_import("TQI-1", _confirm_request())

    assert error.value.status_code == 410
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT status FROM teacher_question_import WHERE import_id='TQI-1'"
        ).fetchone()[0] == "expired"


def test_repeated_confirm_is_idempotent_and_does_not_write_again(tmp_path, monkeypatch) -> None:
    from backend.services.teacher_service import database, question_import_service

    db_path = tmp_path / "idempotent-confirm.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    _seed_import(database, db_path)
    calls = {"count": 0}

    def upsert(items):
        calls["count"] += 1
        return {items[0]["request_id"]: {"question_id": "QNEW", "result": "created"}}

    monkeypatch.setattr(question_import_service, "upsert_confirmed_questions", upsert)

    first = question_import_service.confirm_question_import("TQI-1", _confirm_request())
    second = question_import_service.confirm_question_import("TQI-1", _confirm_request())

    assert second == first
    assert calls["count"] == 1


def test_confirm_rejects_llm_decision_when_solution_is_missing(tmp_path, monkeypatch) -> None:
    from backend.services.teacher_service import database, question_import_service
    from backend.services.teacher_service.models import QuestionImportConfirmRequest

    db_path = tmp_path / "missing-llm.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    _seed_import(database, db_path)
    with database.get_teacher_db() as connection:
        connection.execute("UPDATE teacher_question_import_item SET llm_answer=NULL WHERE item_id='ITEM-1'")
        connection.commit()
    request = QuestionImportConfirmRequest.model_validate({
        "teacher_id": "T001",
        "items": [
            {"item_id": "ITEM-1", "decision": "llm"},
            {"item_id": "ITEM-2", "decision": "existing"},
        ],
    })
    monkeypatch.setattr(
        question_import_service,
        "upsert_confirmed_questions",
        lambda _items: (_ for _ in ()).throw(AssertionError("must not write")),
    )

    with pytest.raises(HTTPException) as error:
        question_import_service.confirm_question_import("TQI-1", request)

    assert error.value.status_code == 422
    assert "LLM" in str(error.value.detail)


def test_graph_upsert_persists_confirmation_metadata(monkeypatch) -> None:
    from backend.services.knowledge_graph_service.models import StandardAnswerUpsertRequest
    from backend.services.knowledge_graph_service.routers import internal_questions

    captured = {}

    class FakeConnection:
        def query(self, query, params):
            captured["query"] = query
            captured["item"] = params["items"][0]
            return [{
                "request_id": "REQ-1",
                "created": True,
                "q": {
                    "id": "QNEW",
                    "text": "1+1=",
                    "answer": "2",
                    "grade": 1,
                    "status": "ready",
                    "standard_solution_status": "ready",
                },
            }]

    monkeypatch.setattr(internal_questions, "neo4j_conn", FakeConnection())
    monkeypatch.setattr(internal_questions, "embed_questions", lambda _items: [None])
    response = internal_questions.upsert_standard_answers(StandardAnswerUpsertRequest.model_validate({
        "items": [{
            "text": "1+1=",
            "answer": "2",
            "explanation": "1加1等于2",
            "request_id": "REQ-1",
            "grade": 1,
            "semester": "上学期",
            "difficulty": "easy",
            "answer_source": "teacher",
            "created_by": "T001",
            "updated_by": "T001",
            "llm_model": "qwen-plus",
            "llm_solved_at": "2026-08-24T00:00:00+00:00",
            "llm_call_count": 1,
        }],
    }))

    assert response.results[0].result == "created"
    assert captured["item"]["grade"] == 1
    assert captured["item"]["answer_source"] == "teacher"
    assert captured["item"]["created_by"] == "T001"
    assert "q.grade = coalesce(item.grade, q.grade)" in captured["query"]
    assert "q.answer_source = coalesce(item.answer_source, q.answer_source)" in captured["query"]
