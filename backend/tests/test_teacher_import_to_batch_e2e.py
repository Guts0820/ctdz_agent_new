from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


def test_confirmed_teacher_questions_can_create_locked_batch(tmp_path, monkeypatch):
    from backend.services.teacher_service import database, homework_batch_service, question_import_service
    from backend.services.teacher_service.models import CreateBatchRequest, QuestionImportConfirmRequest

    database.DATABASE_PATH = str(tmp_path / "teacher-e2e.db")
    database.ensure_question_import_tables()
    with database.get_teacher_db() as connection:
        connection.executescript(
            """
            CREATE TABLE question (
                question_id TEXT PRIMARY KEY, question_description TEXT, question_type TEXT,
                difficulty TEXT, grade TEXT, textbook_version TEXT,
                standard_solve_steps TEXT, answer TEXT
            );
            CREATE TABLE homework_batch (
                batch_id TEXT PRIMARY KEY, class_id TEXT NOT NULL, teacher_id TEXT NOT NULL,
                batch_date TEXT NOT NULL, release_status TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE homework_batch_question (
                batch_id TEXT NOT NULL, question_id TEXT NOT NULL
            );
            """
        )
        connection.commit()
    now = datetime.now(timezone.utc)
    with database.get_teacher_db() as connection:
        connection.execute(
            "INSERT INTO teacher_question_import "
            "(import_id, teacher_id, grade, status, image_sha256, request_key, created_at, expires_at) "
            "VALUES ('TQI-E2E', 'T001', 3, 'review_required', 'hash', 'key', ?, ?)",
            (now.isoformat(), (now + timedelta(hours=1)).isoformat()),
        )
        connection.execute(
            "INSERT INTO teacher_question_import_item "
            "(item_id, import_id, position, question_text, teacher_answer, llm_answer, "
            "llm_solve_steps, solution_source, comparison_status, comparison_reason, comparison_confidence, created_at) "
            "VALUES ('ITEM-E2E', 'TQI-E2E', 1, '1+1=', '2', '2', '[]', 'llm', 'agreed', '等价', 1, ?)",
            (now.isoformat(),),
        )
        connection.commit()

    def fake_upsert(items):
        assert items[0]["text"] == "1+1="
        assert items[0]["answer"] == "2"
        return {items[0]["request_id"]: {"question_id": "Q-E2E", "result": "created"}}

    monkeypatch.setattr(question_import_service, "upsert_confirmed_questions", fake_upsert)
    confirmed = question_import_service.confirm_question_import(
        "TQI-E2E",
        QuestionImportConfirmRequest.model_validate({
            "teacher_id": "T001",
            "items": [{"item_id": "ITEM-E2E", "decision": "teacher", "question_text": "1+1=", "teacher_answer": "2"}],
        }),
    )
    assert confirmed.items[0].question_id == "Q-E2E"

    class ReadyResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "Q-E2E", "status": "ready", "standard_solution_status": "ready"}

    monkeypatch.setattr(homework_batch_service.requests, "get", lambda *args, **kwargs: ReadyResponse())
    monkeypatch.setattr(homework_batch_service, "generate_id", lambda prefix: "HB-E2E")
    monkeypatch.setattr(homework_batch_service, "get_teacher_db", database.get_teacher_db)
    batch = homework_batch_service.create_batch(CreateBatchRequest(
        class_id="CLASS-3-1", teacher_id="T001", batch_date="2026-08-24", question_ids=["Q-E2E"]
    ))

    assert batch.question_ids == ["Q-E2E"]
    assert batch.release_status == "locked"
    with database.get_teacher_db() as connection:
        row = connection.execute(
            "SELECT release_status FROM homework_batch WHERE batch_id = 'HB-E2E'"
        ).fetchone()
        question = connection.execute(
            "SELECT question_description, answer FROM question WHERE question_id = 'Q-E2E'"
        ).fetchone()
    assert row[0] == "locked"
    assert tuple(question) == ("1+1=", "2")
