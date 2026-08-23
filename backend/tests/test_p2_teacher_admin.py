import sqlite3

import pytest


def test_partial_release_rejects_question_outside_batch(monkeypatch):
    from backend.services.teacher_service import homework_batch_service

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=()):
            if "SELECT 1 FROM homework_batch" in query:
                return type("R", (), {"fetchone": lambda self: (1,)})()
            if "SELECT question_id FROM homework_batch_question" in query:
                return type("R", (), {"fetchall": lambda self: [("Q1",)]})()
            raise AssertionError(query)
    monkeypatch.setattr(homework_batch_service, "get_teacher_db", lambda: Connection())
    with pytest.raises(homework_batch_service.HTTPException) as error:
        homework_batch_service.release_partial_batch("HB1", ["Q2"])
    assert error.value.status_code == 422


def test_admin_endpoints_require_admin_role():
    from backend.services.knowledge_graph_service.routers.admin_questions import _require_admin
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _require_admin("teacher")
    assert error.value.status_code == 403
    _require_admin("admin")


def test_admin_audit_table_is_created_and_written(tmp_path, monkeypatch):
    from backend.services.knowledge_graph_service.routers import admin_questions

    db_path = tmp_path / "audit.db"
    monkeypatch.setattr(admin_questions, "DATABASE_PATH", str(db_path))
    admin_questions._audit("review", "A001", "Q1", {"status": "ready"})
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT action, actor, target_id FROM question_audit_log").fetchone()
    assert row == ("review", "A001", "Q1")
