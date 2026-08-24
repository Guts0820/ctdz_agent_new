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
                knowledge_mastery_id TEXT, student_id TEXT, knowledge_id TEXT,
                master_level REAL, priority REAL, correct_count INT, wrong_count INT
            );
            CREATE TABLE review_plan (knowledge_mastery_id TEXT, status TEXT);
            INSERT INTO knowledge_mastery VALUES ('KM1', 'S001', 'K001', 0.35, 88.0, 1, 4);
            INSERT INTO knowledge_mastery VALUES ('KM2', 'S001', 'K002', 0.75, 42.0, 4, 1);
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
    assert response["source"] == "mastery_priority_v1"
    assert response["empty_state"] is None
    assert [item["knowledge_id"] for item in response["data"]] == ["K001", "K002"]
    assert response["data"][0]["mastery_level"] == 35.0
    assert response["data"][0]["stage"] == "remedial"


def test_learning_path_returns_empty_state_without_mastery_records(tmp_path, monkeypatch):
    database = tmp_path / "learning-path-empty.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE knowledge_mastery (
                knowledge_mastery_id TEXT, student_id TEXT, knowledge_id TEXT,
                master_level REAL, priority REAL, correct_count INT, wrong_count INT
            )"""
        )
    monkeypatch.setattr(learning_path, "DATABASE_PATH", str(database))

    response = learning_path.LearningPathRecommender().generate_contract_path("S001")

    assert response["data"] == []
    assert response["empty_state"]


def test_learning_path_logs_generation_metadata_without_learning_content(tmp_path, monkeypatch):
    database = tmp_path / "learning-path-observability.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE knowledge_mastery (
                knowledge_mastery_id TEXT, student_id TEXT, knowledge_id TEXT,
                master_level REAL, priority REAL, correct_count INT, wrong_count INT
            )"""
        )
        connection.execute("INSERT INTO knowledge_mastery VALUES ('KM1', 'S001', 'K001', 0.4, 80, 1, 3)")
    events = []
    monkeypatch.setattr(learning_path, "DATABASE_PATH", str(database))
    monkeypatch.setattr(learning_path.neo4j_conn, "query", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(learning_path, "log_event", lambda event, **fields: events.append((event, fields)))

    learning_path.LearningPathRecommender().generate_contract_path("S001")

    assert events == [("learning_path.generated", {
        "student_id": "S001",
        "path_version": "mastery_priority_v1",
        "candidate_count": 1,
        "selected_count": 1,
        "empty_reason": None,
        "graph_degradation_reason": "neo4j_unavailable",
    })]


def test_learning_path_prioritizes_pending_review_and_known_prerequisites(tmp_path, monkeypatch):
    database = tmp_path / "learning-path-order.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE knowledge_mastery (
                knowledge_mastery_id TEXT, student_id TEXT, knowledge_id TEXT,
                master_level REAL, priority REAL, correct_count INT, wrong_count INT
            );
            CREATE TABLE review_plan (knowledge_mastery_id TEXT, status TEXT);
            INSERT INTO knowledge_mastery VALUES ('KM-PARENT', 'S001', 'K100', 0.45, 20, 2, 2);
            INSERT INTO knowledge_mastery VALUES ('KM-CHILD', 'S001', 'K200', 0.30, 95, 0, 5);
            INSERT INTO knowledge_mastery VALUES ('KM-PENDING', 'S001', 'K300', 0.70, 10, 4, 1);
            INSERT INTO review_plan VALUES ('KM-PENDING', 'pending');
            """
        )
    monkeypatch.setattr(learning_path, "DATABASE_PATH", str(database))
    monkeypatch.setattr(
        learning_path.neo4j_conn,
        "query",
        lambda *_args, **_kwargs: [
            {"knowledge_id": "K100", "title": "前置知识", "prerequisites": []},
            {"knowledge_id": "K200", "title": "薄弱知识", "prerequisites": [{"knowledge_id": "K100", "title": "前置知识"}]},
            {"knowledge_id": "K300", "title": "待复习知识", "prerequisites": []},
        ],
    )

    response = learning_path.LearningPathRecommender().generate_contract_path("S001", limit=3)

    assert [item["knowledge_id"] for item in response["data"]] == ["K300", "K100", "K200"]
    assert response["data"][0]["reason"] == "存在待完成复习计划，建议优先完成。"
    assert response["data"][1]["stage"] == "prerequisite"
    assert response["data"][1]["sequence"] < response["data"][2]["sequence"]


def test_learning_path_keeps_sqlite_order_when_graph_details_are_unavailable(tmp_path, monkeypatch):
    database = tmp_path / "learning-path-graph-down.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE knowledge_mastery (
                knowledge_mastery_id TEXT, student_id TEXT, knowledge_id TEXT,
                master_level REAL, priority REAL, correct_count INT, wrong_count INT
            );
            INSERT INTO knowledge_mastery VALUES ('KM1', 'S001', 'K900', 0.20, 70, 0, 3);
            """
        )
    monkeypatch.setattr(learning_path, "DATABASE_PATH", str(database))
    monkeypatch.setattr(learning_path.neo4j_conn, "query", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError()))

    response = learning_path.LearningPathRecommender().generate_contract_path("S001")

    assert response["data"][0]["knowledge_id"] == "K900"
    assert response["data"][0]["title"] == "K900"
