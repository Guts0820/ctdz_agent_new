"""班级归属判定：教师只能访问本班学生。

判定依据是 ``students.class_id``（Task 1.3 回填）与 ``teacher_class`` 的对应关系。
**学生没有归属班级（``class_id IS NULL``）时一律判定为"不属于任何教师"** —— 授权失败
必须表现为拒绝访问，而不是被某个班顺带放行。
"""

import sqlite3

from backend.shared.config import DATABASE_PATH as CONFIGURED_DATABASE_PATH

# 允许测试 monkeypatch 到临时库
DATABASE_PATH = CONFIGURED_DATABASE_PATH


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def student_class_id(student_id: str) -> str | None:
    """学生归属班级；查不到、未归属或库不可用时返回 None（fail-closed）。"""
    try:
        with _connect() as connection:
            row = connection.execute(
                "SELECT class_id FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None or not row["class_id"]:
        return None
    return str(row["class_id"])


def teacher_owns_class(teacher_id: str | None, class_id: str | None) -> bool:
    if not teacher_id or not class_id:
        return False
    try:
        with _connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM teacher_class WHERE teacher_id = ? AND class_id = ? LIMIT 1",
                (teacher_id, class_id),
            ).fetchone()
    except sqlite3.Error:
        return False
    return row is not None


def teacher_owns_student(teacher_id: str | None, student_id: str) -> bool:
    """学生属于该教师任教的班级才放行；学生未归属班级时拒绝。"""
    class_id = student_class_id(student_id)
    if class_id is None:
        return False
    return teacher_owns_class(teacher_id, class_id)
