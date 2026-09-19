"""角色守卫的单元测试（比端到端更快更稳）。"""

import sqlite3
from pathlib import Path
import pytest
from fastapi import HTTPException

from backend.api_gateway.auth import class_scope
from backend.api_gateway.auth.dependencies import (
    Principal,
    authorize_student,
    authorize_teacher_class,
    require_admin,
)

STUDENT = Principal(account_id="A1", role="student", student_id="S001")
TEACHER = Principal(account_id="A2", role="teacher", teacher_id="T001")
OTHER_TEACHER = Principal(account_id="A3", role="teacher", teacher_id="T002")
ADMIN = Principal(account_id="A9", role="admin")

FIXTURE = """
CREATE TABLE students (student_id TEXT PRIMARY KEY, student_class TEXT, student_grade TEXT, class_id TEXT);
CREATE TABLE teacher_class (
    teacher_id TEXT NOT NULL, class_id TEXT NOT NULL, class_name TEXT NOT NULL,
    grade TEXT, PRIMARY KEY (teacher_id, class_id)
);
INSERT INTO teacher_class VALUES ('T001', 'C001', '一(1)班', '一年级');
INSERT INTO teacher_class VALUES ('T002', 'C005', '三(1)班', '三年级');
INSERT INTO students VALUES ('S001', '一(1)班', '一年级', 'C001');   -- 归属 T001 的班
INSERT INTO students VALUES ('S002', '三(1)班', '三年级', 'C005');   -- 归属 T002 的班
INSERT INTO students VALUES ('S003', '四年级(2)班', '四年级', NULL);  -- 未归属（无对应班级）
"""


@pytest.fixture()
def scope_db(tmp_path: Path, monkeypatch) -> Path:
    database = tmp_path / "scope.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(FIXTURE)
    monkeypatch.setattr(class_scope, "DATABASE_PATH", str(database))
    return database


def test_student_can_only_access_self() -> None:
    authorize_student(STUDENT, "S001")  # 不抛

    with pytest.raises(HTTPException) as error:
        authorize_student(STUDENT, "S002")

    assert error.value.status_code == 403


def test_student_without_a_bound_student_id_is_denied(tmp_path, monkeypatch) -> None:
    """令牌里没有 student_id 的学生账号不能访问任何学生数据。"""
    orphan = Principal(account_id="A1", role="student")

    with pytest.raises(HTTPException) as error:
        authorize_student(orphan, "S001")

    assert error.value.status_code == 403


def test_teacher_can_access_own_class_student(scope_db) -> None:
    authorize_student(TEACHER, "S001")  # 不抛

    with pytest.raises(HTTPException) as error:
        authorize_student(TEACHER, "S002")

    assert error.value.status_code == 403
    assert "非本班" in error.value.detail


def test_teacher_cannot_access_a_student_without_class_ownership(scope_db) -> None:
    """class_id IS NULL 的学生不属于任何教师 —— 必须拒绝，不能顺带放行。"""
    with pytest.raises(HTTPException) as error:
        authorize_student(TEACHER, "S003")

    assert error.value.status_code == 403


def test_teacher_cannot_access_an_unknown_student(scope_db) -> None:
    with pytest.raises(HTTPException) as error:
        authorize_student(TEACHER, "S999")

    assert error.value.status_code == 403


def test_admin_bypasses_scope_checks(scope_db) -> None:
    authorize_student(ADMIN, "S999")  # 不抛
    authorize_teacher_class(ADMIN, "C999")  # 不抛
    require_admin(ADMIN)  # 不抛


def test_teacher_cannot_call_admin_only_endpoint() -> None:
    with pytest.raises(HTTPException) as error:
        require_admin(TEACHER)

    assert error.value.status_code == 403


def test_student_cannot_call_admin_only_endpoint() -> None:
    with pytest.raises(HTTPException) as error:
        require_admin(STUDENT)

    assert error.value.status_code == 403


def test_teacher_class_scope(scope_db) -> None:
    authorize_teacher_class(TEACHER, "C001")  # 不抛

    with pytest.raises(HTTPException) as error:
        authorize_teacher_class(TEACHER, "C005")

    assert error.value.status_code == 403


def test_student_cannot_access_the_class_dimension(scope_db) -> None:
    with pytest.raises(HTTPException) as error:
        authorize_teacher_class(STUDENT, "C001")

    assert error.value.status_code == 403
    assert error.value.detail == "需要教师权限"


def test_teacher_without_a_class_id_is_denied(scope_db) -> None:
    """teacher 令牌缺 teacher_id，或者传了空 class_id，都不能放行。"""
    anonymous_teacher = Principal(account_id="A4", role="teacher")

    with pytest.raises(HTTPException):
        authorize_student(anonymous_teacher, "S001")
    with pytest.raises(HTTPException) as error:
        authorize_teacher_class(TEACHER, None)

    assert error.value.status_code == 403


def test_scope_helpers_are_fail_closed(monkeypatch, tmp_path) -> None:
    """库不可用时也必须是拒绝，而不是抛 500 或放行。"""
    monkeypatch.setattr(class_scope, "DATABASE_PATH", str(tmp_path / "missing.db"))

    assert class_scope.student_class_id("S001") is None
    assert class_scope.teacher_owns_student("T001", "S001") is False
