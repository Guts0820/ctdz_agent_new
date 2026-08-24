import sqlite3

from backend.services.review_service.datahub.core import learning_path


def test_normalize_student_id_accepts_current_and_legacy_formats():
    assert learning_path.normalize_student_id("S001") == "S001"
    assert learning_path.normalize_student_id("S-0001") == "S001"
    assert learning_path.normalize_student_id(1) == "S001"


def test_learning_path_uses_sqlite_mastery_and_returns_stable_contract(tmp_path, monkeypatch):
    database = tmp_path / "learning-path.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE knowledge_mastery (
                student_id TEXT, knowledge_id TEXT, master_level REAL, priority REAL
            );
            INSERT INTO knowledge_mastery VALUES ('S001', 'K001', 0.35, 88.0);
            INSERT INTO knowledge_mastery VALUES ('S001', 'K002', 0.75, 42.0);
            """
        )
    monkeypatch.setattr(learning_path, "DATABASE_PATH", str(database))
    monkeypatch.setattr(
        learning_path.neo4j_conn,
        "query",
        lambda *_args, **_kwargs: [{"knowledge_id": "K001", "title": "数一数", "prerequisites": []}],
    )

    response = learning_path.LearningPathRecommender().generate_contract_path("S-0001")

    assert response["student_id"] == "S001"
    assert response["source"] == "sqlite_mastery_v1"
    assert response["empty_state"] is None
    assert [item["knowledge_id"] for item in response["data"]] == ["K001", "K002"]
    assert response["data"][0]["mastery_level"] == 35.0
    assert response["data"][0]["stage"] == "remedial"


def test_learning_path_returns_empty_state_without_mastery_records(tmp_path, monkeypatch):
    database = tmp_path / "learning-path-empty.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE knowledge_mastery (student_id TEXT, knowledge_id TEXT, master_level REAL, priority REAL)"
        )
    monkeypatch.setattr(learning_path, "DATABASE_PATH", str(database))

    response = learning_path.LearningPathRecommender().generate_contract_path("S001")

    assert response["data"] == []
    assert response["empty_state"]
