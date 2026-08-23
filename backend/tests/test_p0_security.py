import sqlite3


def test_student_question_response_has_no_answer_fields():
    from backend.services.review_service.review.schemas.review import QuestionForStudent

    fields = set(QuestionForStudent.model_fields)
    assert {"answer", "answer_steps", "standard_answer", "standard_solve_steps"}.isdisjoint(fields)


def test_gateway_release_lookup_fails_closed(monkeypatch):
    from backend.api_gateway.services import submission_service

    def unavailable_db():
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(submission_service, "_get_db", unavailable_db)
    assert submission_service._is_answer_released("Q1") is False


def test_review_release_lookup_fails_closed(monkeypatch):
    from backend.services.review_service.review.services.session_service import SessionService

    monkeypatch.setattr("sqlite3.connect", lambda *_args, **_kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("down")))
    assert SessionService._is_answer_released("Q1") is False

