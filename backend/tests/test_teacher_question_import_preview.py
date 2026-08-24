import sqlite3


def _ocr_payload() -> dict:
    return {
        "analysis_input": {
            "schema_version": "1.0",
            "questions": [
                {
                    "question": {"text": "0.8×0.02=", "explanation": "计算小数乘法。"},
                    "student_answer": {"text": "0.016"},
                },
                {
                    "question": {"text": "12÷3=", "explanation": "计算除法。"},
                    "student_answer": {"text": "5"},
                },
            ],
            "confidence": 0.99,
            "review_required": False,
        },
        "engine": "qwen-vl-plus",
        "status": "success",
    }


def test_preview_route_is_exposed_by_teacher_service_and_gateway() -> None:
    from backend.api_gateway.app import app as gateway_app
    from backend.services.teacher_service.main import app as teacher_app

    assert "/internal/api/v1/teacher/question-imports/preview" in teacher_app.openapi()["paths"]
    assert "/api/v1/teacher/question-imports/preview" in gateway_app.openapi()["paths"]


def test_numeric_answer_equivalence_is_deterministic() -> None:
    from backend.services.teacher_service.answer_comparison import compare_answers

    result = compare_answers("1/2", "0.5")

    assert result.status == "agreed"
    assert result.confidence == 1.0


def test_preview_persists_review_items_without_writing_question_bank(tmp_path, monkeypatch) -> None:
    from backend.services.teacher_service import database, question_import_service

    db_path = tmp_path / "preview.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(question_import_service, "recognize_standard_answer_image", lambda *_args: _ocr_payload())
    solutions = iter([
        {"answer": "0.016", "solve_steps": ["8×2=16", "小数点共三位"], "difficulty": "easy"},
        {"answer": "4", "solve_steps": ["12÷3=4"], "difficulty": "easy"},
    ])
    monkeypatch.setattr(question_import_service, "solve_question_with_llm", lambda **_kwargs: next(solutions))
    monkeypatch.setattr(question_import_service, "find_existing_question", lambda _text: None)

    result = question_import_service.create_question_import_preview(
        image_bytes=b"image",
        filename="answers.png",
        content_type="image/png",
        teacher_id="T001",
        grade=3,
        semester="上学期",
    )

    assert result.status == "review_required"
    assert [item.comparison_status for item in result.items] == ["agreed", "conflict"]
    assert result.items[0].llm_solve_steps == ["8×2=16", "小数点共三位"]
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM teacher_question_import").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM teacher_question_import_item").fetchone()[0] == 2
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "question" not in tables


def test_repeated_preview_reuses_staged_result_without_repeating_llm(tmp_path, monkeypatch) -> None:
    from backend.services.teacher_service import database, question_import_service

    db_path = tmp_path / "idempotent.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(question_import_service, "recognize_standard_answer_image", lambda *_args: {
        "analysis_input": {
            "questions": [{
                "question": {"text": "1+1=", "explanation": ""},
                "student_answer": {"text": "2"},
            }],
            "confidence": 0.99,
            "review_required": False,
        },
        "engine": "qwen-vl-plus",
        "status": "success",
    })
    calls = {"count": 0}

    def solve(**_kwargs):
        calls["count"] += 1
        return {"answer": "2", "solve_steps": ["1+1=2"], "difficulty": "easy"}

    monkeypatch.setattr(question_import_service, "solve_question_with_llm", solve)
    monkeypatch.setattr(question_import_service, "find_existing_question", lambda _text: None)
    arguments = {
        "image_bytes": b"same-image",
        "filename": "answers.png",
        "content_type": "image/png",
        "teacher_id": "T001",
        "grade": 1,
        "semester": None,
    }

    first = question_import_service.create_question_import_preview(**arguments)
    second = question_import_service.create_question_import_preview(**arguments)

    assert first.import_id == second.import_id
    assert calls["count"] == 1


def test_llm_failure_keeps_teacher_result_for_manual_review(tmp_path, monkeypatch) -> None:
    from backend.services.teacher_service import database, question_import_service

    db_path = tmp_path / "llm-failed.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(question_import_service, "recognize_standard_answer_image", lambda *_args: {
        "analysis_input": {
            "questions": [{
                "question": {"text": "2+3=", "explanation": ""},
                "student_answer": {"text": "5"},
            }],
            "confidence": 0.99,
            "review_required": False,
        }
    })
    monkeypatch.setattr(
        question_import_service,
        "solve_question_with_llm",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("LLM unavailable")),
    )
    monkeypatch.setattr(question_import_service, "find_existing_question", lambda _text: None)

    result = question_import_service.create_question_import_preview(
        image_bytes=b"image",
        filename="answers.png",
        content_type="image/png",
        teacher_id="T001",
        grade=1,
        semester=None,
    )

    assert result.items[0].teacher_answer == "5"
    assert result.items[0].llm_answer is None
    assert result.items[0].comparison_status == "llm_failed"


def test_existing_ready_question_reuses_solution_without_calling_solver(tmp_path, monkeypatch) -> None:
    from backend.services.teacher_service import database, question_import_service

    db_path = tmp_path / "existing.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(question_import_service, "recognize_standard_answer_image", lambda *_args: {
        "analysis_input": {
            "questions": [{
                "question": {"text": "6×7=", "explanation": ""},
                "student_answer": {"text": "42"},
            }],
            "confidence": 0.99,
            "review_required": False,
        }
    })
    monkeypatch.setattr(question_import_service, "find_existing_question", lambda _text: {
        "id": "Q42",
        "answer": "42",
        "answer_steps": "使用乘法口诀六七四十二",
        "difficulty": 1,
        "status": "ready",
        "standard_solution_status": "ready",
    })
    monkeypatch.setattr(
        question_import_service,
        "solve_question_with_llm",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("已有题不得重复调用解题 LLM")),
    )

    result = question_import_service.create_question_import_preview(
        image_bytes=b"existing-image",
        filename="answers.png",
        content_type="image/png",
        teacher_id="T001",
        grade=1,
        semester=None,
    )

    assert result.items[0].solution_source == "existing"
    assert result.items[0].existing_question_id == "Q42"
    assert result.items[0].llm_answer == "42"
