import sqlite3

from backend.shared.config import DATABASE_PATH


def get_teacher_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


QUESTION_IMPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS teacher_question_import (
    import_id VARCHAR(32) PRIMARY KEY,
    teacher_id VARCHAR(32) NOT NULL,
    grade INTEGER NOT NULL,
    semester VARCHAR(20),
    status VARCHAR(32) NOT NULL,
    image_sha256 VARCHAR(64) NOT NULL,
    request_key VARCHAR(64) NOT NULL UNIQUE,
    ocr_confidence FLOAT,
    ocr_engine VARCHAR(100),
    error_message TEXT,
    created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    confirmed_at DATETIME
);

CREATE TABLE IF NOT EXISTS teacher_question_import_item (
    item_id VARCHAR(32) PRIMARY KEY,
    import_id VARCHAR(32) NOT NULL,
    position INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    teacher_answer TEXT NOT NULL,
    teacher_explanation TEXT,
    llm_answer TEXT,
    llm_solve_steps TEXT,
    llm_difficulty VARCHAR(20),
    solution_source VARCHAR(20) NOT NULL DEFAULT 'none',
    comparison_status VARCHAR(20) NOT NULL,
    comparison_reason TEXT,
    comparison_confidence FLOAT NOT NULL DEFAULT 0,
    existing_question_id VARCHAR(64),
    decision VARCHAR(20),
    confirmed_question_id VARCHAR(64),
    confirm_result VARCHAR(20),
    llm_model VARCHAR(100),
    llm_solved_at DATETIME,
    created_at DATETIME NOT NULL,
    UNIQUE(import_id, position),
    FOREIGN KEY (import_id) REFERENCES teacher_question_import(import_id)
);

CREATE INDEX IF NOT EXISTS idx_teacher_question_import_teacher_status
ON teacher_question_import(teacher_id, status);
"""


def ensure_question_import_tables() -> None:
    with get_teacher_db() as connection:
        connection.executescript(QUESTION_IMPORT_SCHEMA)
        table_columns = {
            "teacher_question_import": {
                "confirmed_at": "DATETIME",
            },
            "teacher_question_import_item": {
                "confirmed_question_id": "VARCHAR(64)",
                "confirm_result": "VARCHAR(20)",
                "llm_model": "VARCHAR(100)",
                "llm_solved_at": "DATETIME",
            },
        }
        for table, columns in table_columns.items():
            existing = {
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for column, declaration in columns.items():
                if column not in existing:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
        connection.commit()
