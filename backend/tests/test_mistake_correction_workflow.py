import sqlite3

import pytest
from fastapi import HTTPException

from backend.api_gateway.models import MistakeCorrectionRequest
from backend.api_gateway.routers.mistake_corrections import router
from backend.api_gateway.services import mistake_correction_service as correction
from backend.api_gateway.services import student_statistics_service as statistics


def _connect(database):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    return connection


def test_gateway_exposes_real_mistake_correction_route():
    paths = {route.path for route in router.routes}
    assert "/api/v1/mistakes/{mistake_case_id}/correction" in paths


@pytest.fixture
def correction_database(tmp_path, monkeypatch):
    database = tmp_path / "correction.db"
    with _connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE mistake_case (
                mistake_case_id TEXT PRIMARY KEY, student_id TEXT, question_id TEXT,
                current_status TEXT, created_at TEXT
            );
            CREATE TABLE mistake_case_knowledge (mistake_case_id TEXT, knowledge_id TEXT);
            CREATE TABLE question_knowledge_mapping (question_id TEXT, knowledge_id TEXT);
            CREATE TABLE question (question_id TEXT PRIMARY KEY, question_description TEXT);
            CREATE TABLE teaching_content (mistake_case_id TEXT, master_level REAL, created_at TEXT);
            CREATE TABLE answer_history (
                answer_history_id TEXT PRIMARY KEY, student_id TEXT, question_id TEXT,
                mistake_case_id TEXT, submit_type TEXT, submit_count INT,
                ocr_question TEXT, student_ocr_answer TEXT, core_error_type TEXT,
                is_correct INT, submitted_at TEXT
            );
            INSERT INTO question VALUES ('Q1', '25+38等于多少？');
            INSERT INTO question_knowledge_mapping VALUES ('Q1', 'K1');
            INSERT INTO mistake_case VALUES ('MC1', 'S1', 'Q1', 'correcting', '2026-08-20T09:00:00');
            INSERT INTO mistake_case_knowledge VALUES ('MC1', 'K1');
            INSERT INTO answer_history VALUES (
                'AH1', 'S1', 'Q1', 'MC1', '首次错题', 1,
                '25+38等于多少？', '53', '计算错误', 0, '2026-08-20T09:00:00'
            );
            """
        )

    monkeypatch.setattr(correction, "get_gateway_db", lambda: _connect(database))
    monkeypatch.setattr(statistics, "get_gateway_db", lambda: _connect(database))
    return database


def _install_analysis(monkeypatch, database, *, answer_history_id, is_correct):
    def analyze(payload):
        with _connect(database) as connection:
            connection.execute(
                """INSERT INTO answer_history
                   (answer_history_id, student_id, question_id, submit_type, submit_count,
                    ocr_question, student_ocr_answer, is_correct, submitted_at)
                   VALUES (?, ?, ?, '首次错题', 1, ?, ?, ?, '2026-08-20T10:00:00')""",
                (
                    answer_history_id, payload["student_id"], payload["question_id"],
                    payload["original_question"], payload["student_write"], int(is_correct),
                ),
            )
            connection.commit()
        return {
            "answer_history_id": answer_history_id,
            "question_id": payload["question_id"],
            "knowledge_id": "K1",
            "judge_result": "correct" if is_correct else "wrong",
            "confidence": 0.98,
            "step_feedback": "订正判定完成",
        }

    monkeypatch.setattr(correction, "analyze_submission", analyze)
    monkeypatch.setattr(correction, "update_state", lambda *_args: {
        "master_level": 0.72, "mastery": 72.0, "priority": 41.0,
        "next_action": "practice",
    })


def test_correct_correction_closes_mistake_and_records_submit_type(
    correction_database, monkeypatch
):
    _install_analysis(monkeypatch, correction_database, answer_history_id="AH2", is_correct=True)
    response = correction.process_mistake_correction(
        "MC1",
        MistakeCorrectionRequest(original_question="25+38等于多少？", new_answer="63"),
    )
    assert response.is_correct is True
    assert response.mistake_status == "corrected"
    assert response.submit_type == "错题订正"
    assert response.submit_count == 2
    assert response.teaching_mode == "STANDARD"
    assert response.teaching_difficulty == "medium"
    assert response.state_sync_status == "updated"
    with _connect(correction_database) as connection:
        history = connection.execute(
            "SELECT mistake_case_id, submit_type, submit_count FROM answer_history WHERE answer_history_id='AH2'"
        ).fetchone()
        status = connection.execute(
            "SELECT current_status FROM mistake_case WHERE mistake_case_id='MC1'"
        ).fetchone()[0]
    assert tuple(history) == ("MC1", "错题订正", 2)
    assert status == "corrected"

    wrong_answers = statistics.get_wrong_answers("S1")["data"]
    assert wrong_answers[0]["mistake_case_id"] == "MC1"
    assert wrong_answers[0]["reviewed"] is True
    assert wrong_answers[0]["correction_answer"] == "63"


def test_wrong_correction_remains_open_and_can_be_retried(correction_database, monkeypatch):
    _install_analysis(monkeypatch, correction_database, answer_history_id="AH2", is_correct=False)
    response = correction.process_mistake_correction(
        "MC1",
        MistakeCorrectionRequest(original_question="25+38等于多少？", new_answer="62"),
    )
    assert response.is_correct is False
    assert response.mistake_status == "correcting"
    assert response.submit_count == 2

    _install_analysis(monkeypatch, correction_database, answer_history_id="AH3", is_correct=True)
    retry = correction.process_mistake_correction(
        "MC1",
        MistakeCorrectionRequest(original_question="25+38等于多少？", new_answer="63"),
    )
    assert retry.is_correct is True
    assert retry.submit_count == 3


def test_completed_mistake_rejects_duplicate_correction(correction_database):
    with _connect(correction_database) as connection:
        connection.execute("UPDATE mistake_case SET current_status='corrected' WHERE mistake_case_id='MC1'")
        connection.commit()
    with pytest.raises(HTTPException) as caught:
        correction.process_mistake_correction(
            "MC1",
            MistakeCorrectionRequest(original_question="25+38等于多少？", new_answer="63"),
        )
    assert caught.value.status_code == 409


def test_correction_rejects_question_that_does_not_belong_to_case(correction_database):
    with pytest.raises(HTTPException) as caught:
        correction.process_mistake_correction(
            "MC1",
            MistakeCorrectionRequest(original_question="另一道题", new_answer="63"),
        )
    assert caught.value.status_code == 422
