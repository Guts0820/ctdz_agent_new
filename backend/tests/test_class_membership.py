"""学生班级归属可判定（Phase 1 授权的前置数据条件）。"""

import sqlite3
from pathlib import Path

import pytest

from backend.tools import init_sqlite_database
from backend.tools.migrations import backfill_student_class_id as backfill


FIXTURE_SQL = """
CREATE TABLE students (
    student_id TEXT PRIMARY KEY, student_name TEXT, student_class TEXT,
    student_grade TEXT, class_id TEXT
);
CREATE TABLE teacher_class (
    teacher_id TEXT NOT NULL, class_id TEXT NOT NULL, class_name TEXT NOT NULL,
    grade TEXT, PRIMARY KEY (teacher_id, class_id)
);
CREATE TABLE homework_batch (
    batch_id TEXT PRIMARY KEY, class_id TEXT, teacher_id TEXT, batch_date TEXT
);
INSERT INTO teacher_class VALUES ('T001', 'C001', '一(1)班', '一年级');
INSERT INTO teacher_class VALUES ('T002', 'C004', '二(1)班', '二年级');
INSERT INTO teacher_class VALUES ('T003', 'C005', '三(1)班', '三年级');
INSERT INTO students VALUES ('S001', '甲', '一(1)班', '一年级', NULL);
INSERT INTO students VALUES ('S-0001', '乙', '三年级(1)班', '三年级', NULL);
INSERT INTO students VALUES ('S-0003', '丙', '四年级(2)班', '四年级', NULL);
INSERT INTO homework_batch VALUES ('HB-1', '1年级一班', 'T001', '2026-09-01');
INSERT INTO homework_batch VALUES ('HB-2', 'C-001', 'T001', '2026-09-02');
INSERT INTO homework_batch VALUES ('HB-3', 'C005', 'T003', '2026-09-03');
INSERT INTO homework_batch VALUES ('HB-4', '五年级三班', 'T009', '2026-09-04');
INSERT INTO homework_batch VALUES ('HB-5', '一(1)班', 'T001', '2026-09-05');
"""


def build_fixture(tmp_path: Path) -> Path:
    database = tmp_path / "class-membership.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(FIXTURE_SQL)
    return database


def test_init_schema_exposes_students_class_id_column() -> None:
    with sqlite3.connect(":memory:") as connection:
        connection.executescript(init_sqlite_database.SCHEMA)

        columns = {row[1] for row in connection.execute("PRAGMA table_info(students)")}

    assert "class_id" in columns


def test_init_database_creates_the_class_id_index_and_is_repeatable(tmp_path, monkeypatch) -> None:
    """索引不能写在 SCHEMA 里：老库的 students 表没有 class_id 时 executescript 会整段失败。"""
    database = tmp_path / "init.db"
    monkeypatch.setattr(init_sqlite_database, "DATABASE", str(database))
    monkeypatch.setattr(init_sqlite_database, "KNOWLEDGE_CSV", str(tmp_path / "missing.csv"))

    init_sqlite_database.init_database()
    init_sqlite_database.init_database()  # 重复执行必须安全（start_all 每次都会跑）

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(students)")}
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(students)")}

    assert "class_id" in columns
    assert "idx_students_class" in indexes


def test_init_database_migrates_a_students_table_without_class_id(tmp_path, monkeypatch) -> None:
    """老库（含仓库里被跟踪的 example_db.db）没有 class_id 列，init 必须先补列。"""
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """CREATE TABLE students (
                   student_id VARCHAR(32) PRIMARY KEY,
                   student_birthdate DATE,
                   student_name VARCHAR(50),
                   student_gender VARCHAR(10),
                   student_school VARCHAR(100),
                   student_class VARCHAR(50),
                   student_grade VARCHAR(20),
                   created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                   updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
               );
               INSERT INTO students (student_id, student_class, student_grade)
                   VALUES ('S-0001', '三年级(1)班', '三年级');"""
        )
    monkeypatch.setattr(init_sqlite_database, "DATABASE", str(database))
    monkeypatch.setattr(init_sqlite_database, "KNOWLEDGE_CSV", str(tmp_path / "missing.csv"))

    init_sqlite_database.init_database()

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(students)")}
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(students)")}
        student = connection.execute(
            "SELECT student_id, student_class, class_id FROM students WHERE student_id = 'S-0001'"
        ).fetchall()

    assert "class_id" in columns
    assert "idx_students_class" in indexes
    # 存量行不被破坏（种子数据会补插其它学生，这里只断言原有那条）
    assert student == [("S-0001", "三年级(1)班", None)]


def test_parse_class_label_handles_every_observed_writing_style() -> None:
    assert backfill.parse_class_label("一(1)班", "一年级") == (1, 1)
    assert backfill.parse_class_label("一(1)班") == (1, 1)  # 年级写在括号前的低年级写法
    assert backfill.parse_class_label("三年级(1)班", "三年级") == (3, 1)
    assert backfill.parse_class_label("四年级(2)班", "四年级") == (4, 2)
    assert backfill.parse_class_label("1年级一班") == (1, 1)
    assert backfill.parse_class_label("五年级三班") == (5, 3)
    assert backfill.parse_class_label("三(1)班", "三年级") == (3, 1)


def test_parse_class_label_returns_none_for_unknown_input() -> None:
    assert backfill.parse_class_label("") is None
    assert backfill.parse_class_label(None) is None
    assert backfill.parse_class_label("阳光小学") is None
    assert backfill.parse_class_label("三班") is None  # 没有年级信息，不能瞎猜


def test_resolve_class_id_prefers_canonical_ids_and_parses_labels(tmp_path: Path) -> None:
    database = build_fixture(tmp_path)
    with sqlite3.connect(database) as connection:
        index = backfill.build_class_index(connection)

    assert index == {(1, 1): "C001", (2, 1): "C004", (3, 1): "C005"}
    assert backfill.resolve_class_id("一(1)班", "一年级", index) == "C001"
    assert backfill.resolve_class_id("三年级(1)班", "三年级", index) == "C005"
    assert backfill.resolve_class_id("C-001", None, index) == "C001"
    assert backfill.resolve_class_id("1年级一班", None, index) == "C001"
    assert backfill.resolve_class_id("四年级(2)班", "四年级", index) is None


def test_backfill_assigns_students_and_reports_the_unmatched(tmp_path: Path) -> None:
    database = build_fixture(tmp_path)
    mismatch_csv = tmp_path / "class_mismatch.csv"

    summary = backfill.backfill(str(database), mismatch_path=mismatch_csv)

    assert summary["students_total"] == 3
    assert summary["students_assigned"] == 2
    assert summary["students_unassigned"] == 1
    with sqlite3.connect(database) as connection:
        students = dict(connection.execute("SELECT student_id, class_id FROM students"))
        batches = dict(connection.execute("SELECT batch_id, class_id FROM homework_batch"))
    assert students == {"S001": "C001", "S-0001": "C005", "S-0003": None}
    assert batches == {
        "HB-1": "C001",
        "HB-2": "C001",
        "HB-3": "C005",
        "HB-4": "五年级三班",
        "HB-5": "C001",
    }

    csv_text = mismatch_csv.read_text(encoding="utf-8")
    assert "S-0003" in csv_text and "四年级(2)班" in csv_text
    assert "HB-4" in csv_text
    assert "五年级三班" in csv_text
    assert "S-0001" not in csv_text


def test_unmatched_students_are_left_null_instead_of_guessed(tmp_path: Path) -> None:
    """无法归属必须显式留空：授权层据此拒绝，而不是被分到某个班。"""
    database = build_fixture(tmp_path)

    backfill.backfill(str(database), mismatch_path=tmp_path / "m.csv")

    with sqlite3.connect(database) as connection:
        unresolved = connection.execute(
            "SELECT student_id FROM students WHERE class_id IS NULL"
        ).fetchall()
    assert unresolved == [("S-0003",)]


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    database = build_fixture(tmp_path)
    mismatch_csv = tmp_path / "class_mismatch.csv"

    first = backfill.backfill(str(database), mismatch_path=mismatch_csv)
    second = backfill.backfill(str(database), mismatch_path=mismatch_csv)

    assert first["students_assigned"] == second["students_assigned"] == 2
    assert second["batches_normalized"] == 0  # 第二次没有可改的行
    assert first["students_unassigned"] == second["students_unassigned"] == 1


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    database = build_fixture(tmp_path)

    backfill.backfill(str(database), dry_run=True, mismatch_path=tmp_path / "m.csv")

    with sqlite3.connect(database) as connection:
        assert dict(connection.execute("SELECT student_id, class_id FROM students")) == {
            "S001": None,
            "S-0001": None,
            "S-0003": None,
        }


def test_ensure_schema_migrates_a_legacy_database(tmp_path: Path) -> None:
    """老库没有 class_id 列，迁移要把它补上并建索引。"""
    legacy = tmp_path / "legacy.db"
    with sqlite3.connect(legacy) as connection:
        connection.execute(
            "CREATE TABLE students (student_id TEXT PRIMARY KEY, student_class TEXT, student_grade TEXT)"
        )

    with sqlite3.connect(legacy) as connection:
        applied = backfill.ensure_schema(connection)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(students)")}

    assert "class_id" in columns
    assert any("ADD COLUMN class_id" in statement for statement in applied)


def test_backfill_requires_a_teacher_class_table(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    with sqlite3.connect(empty) as connection:
        connection.execute(
            "CREATE TABLE students (student_id TEXT PRIMARY KEY, student_class TEXT, student_grade TEXT, class_id TEXT)"
        )

    with pytest.raises(sqlite3.OperationalError):
        backfill.backfill(str(empty), mismatch_path=tmp_path / "m.csv")
