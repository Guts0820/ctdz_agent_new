from types import SimpleNamespace


def test_question_fingerprint_collapses_ocr_spacing_and_punctuation() -> None:
    from backend.services.knowledge_graph_service.routers.internal_questions import (
        normalize_question_text,
        question_fingerprint,
    )

    assert normalize_question_text(" 0.8 × 0.02 = ") == normalize_question_text("0．8*0.02=")
    assert question_fingerprint("0.8 × 0.02 =") == question_fingerprint("0．8*0.02=")


def test_standard_answer_upsert_merges_by_fingerprint_and_marks_ready(monkeypatch) -> None:
    from backend.services.knowledge_graph_service.routers import internal_questions
    from backend.services.knowledge_graph_service.models import StandardAnswerUpsertRequest

    captured = {}

    class FakeConnection:
        def query(self, query, params):
            captured["query"] = query
            captured["params"] = params
            return [{"q": {"id": "TQ1", "text": "1+1=", "answer": "2", "status": "ready"}}]

    monkeypatch.setattr(internal_questions, "neo4j_conn", FakeConnection())
    monkeypatch.setattr(internal_questions, "embed_questions", lambda items: [None for _ in items])
    response = internal_questions.upsert_standard_answers(
        StandardAnswerUpsertRequest(items=[{"text": "1 + 1 =", "answer": "2"}])
    )

    assert response.imported_count == 1
    assert "MERGE (q:Question {fingerprint: item.fingerprint})" in captured["query"]
    assert "q.standard_solution_status = 'ready'" in captured["query"]
    assert len(captured["params"]["items"][0]["fingerprint"]) == 64


def test_teacher_batch_rejects_pending_question(monkeypatch) -> None:
    from fastapi import HTTPException
    from backend.services.teacher_service import homework_batch_service

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "Q1", "status": "pending", "standard_solution_status": "processing"}

    monkeypatch.setattr(homework_batch_service.requests, "get", lambda *args, **kwargs: FakeResponse())
    try:
        homework_batch_service._validate_ready_questions(["Q1"])
    except HTTPException as error:
        assert error.status_code == 422
        assert "尚未完成标准解题" in str(error.detail)
    else:
        raise AssertionError("pending question must not be assigned")


def test_analysis_request_forwards_current_batch_question_scope(monkeypatch) -> None:
    from backend.api_gateway.models import SubmitRequest
    from backend.api_gateway.services import submission_service

    monkeypatch.setattr(submission_service, "_batch_question_ids", lambda batch_id: ["Q1", "Q2"])
    prepared = submission_service.prepare_judging_input(
        SubmitRequest(
            student_id="S1",
            batch_id="HB1",
            original_question="题干",
            student_write="答案",
        )
    )
    assert prepared["analysis_request"]["allowed_question_ids"] == ["Q1", "Q2"]
