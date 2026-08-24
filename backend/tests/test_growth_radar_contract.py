import sqlite3
from datetime import datetime

from backend.services.review_service.datahub.core import ability_mapping, growth_report
from backend.services.review_service.datahub.models import GrowthReportResponse


class _StaticLearningPath:
    def generate_contract_path(self, _student_id):
        return {"data": [{"knowledge_id": "K004"}]}


def test_ability_mapping_schema_is_versioned_and_seeded(tmp_path):
    database = tmp_path / "ability-mapping.db"

    ability_mapping.ensure_ability_mapping_schema(database)
    ability_mapping.ensure_ability_mapping_schema(database)

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT knowledge_id, dimension, weight, mapping_version, source "
            "FROM knowledge_ability_mapping WHERE knowledge_id IN ('K004', 'K005') ORDER BY knowledge_id"
        ).fetchall()
    assert rows == [
        ("K004", "operation", 1.0, "ability-map-v1", "seed"),
        ("K005", "spatial", 1.0, "ability-map-v1", "seed"),
    ]


def test_growth_report_contract_normalizes_student_and_never_invents_scores(tmp_path, monkeypatch):
    database = tmp_path / "growth-report.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE knowledge_mastery (
                student_id TEXT, knowledge_id TEXT, master_level REAL, priority REAL,
                correct_count INTEGER, wrong_count INTEGER
            )"""
        )
        connection.execute("INSERT INTO knowledge_mastery VALUES ('S001', 'K999', 0.5, 50, 1, 1)")
    monkeypatch.setattr(growth_report, "DATABASE_PATH", str(database))

    report = growth_report.GrowthReportContractService().generate_contract_report("S-0001")

    assert report["student_id"] == "S001"
    assert report["source"] == "growth_report_v1"
    assert report["empty_state"] is None
    assert [item["id"] for item in report["radar"]["dimensions"]] == [
        "operation", "logic", "spatial", "application", "resilience",
    ]
    assert all(item["score"] is None for item in report["radar"]["dimensions"])
    assert all(item["status"] == "insufficient_data" for item in report["radar"]["dimensions"])


def test_growth_report_contract_has_a_non_error_empty_state(tmp_path, monkeypatch):
    database = tmp_path / "growth-report-empty.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE knowledge_mastery (student_id TEXT)")
    monkeypatch.setattr(growth_report, "DATABASE_PATH", str(database))

    report = growth_report.GrowthReportContractService().generate_contract_report("S001")

    assert report["radar"]["empty_state"]
    assert report["empty_state"]


def test_growth_report_aggregates_real_mastery_and_learning_behaviors(tmp_path, monkeypatch):
    database = tmp_path / "growth-report-facts.db"
    now = datetime.now().isoformat()
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE knowledge_mastery (
                student_id TEXT, knowledge_id TEXT, master_level REAL, priority REAL,
                correct_count INTEGER, wrong_count INTEGER
            );
            CREATE TABLE knowledge (knowledge_id TEXT, knowledge_name TEXT, knowledge_scope TEXT);
            CREATE TABLE question_knowledge_mapping (question_id TEXT, knowledge_id TEXT);
            CREATE TABLE answer_history (
                student_id TEXT, question_id TEXT, is_correct INTEGER, error_tags TEXT, submitted_at TEXT
            );
            CREATE TABLE mistake_case (student_id TEXT, current_status TEXT);
            CREATE TABLE review2_plan (student_id TEXT, status TEXT);
            CREATE TABLE review2_session (id TEXT, student_id TEXT);
            CREATE TABLE review2_attempt (session_id TEXT, submitted_at TEXT);
            INSERT INTO knowledge_mastery VALUES ('S001', 'K004', 0.8, 20, 4, 1);
            INSERT INTO knowledge_mastery VALUES ('S001', 'K005', 0.6, 40, 2, 2);
            INSERT INTO knowledge_mastery VALUES ('S001', 'K011', 0.9, 30, 5, 1);
            INSERT INTO knowledge VALUES ('K005', '立体图形', '认识立体图形');
            INSERT INTO question_knowledge_mapping VALUES ('Q-APP', 'K011');
            INSERT INTO answer_history VALUES ('S001', 'Q-APP', 0, '[{"level1":"审题"}]', '%s');
            INSERT INTO answer_history VALUES ('S001', 'Q-APP', 1, NULL, '%s');
            INSERT INTO mistake_case VALUES ('S001', 'corrected');
            INSERT INTO review2_plan VALUES ('S001', 'completed');
            """ % (now, now)
        )
    ability_mapping.ensure_ability_mapping_schema(database)
    events = []
    monkeypatch.setattr(growth_report, "DATABASE_PATH", str(database))
    monkeypatch.setattr(growth_report, "log_event", lambda event, **fields: events.append((event, fields)))

    report = growth_report.GrowthReportContractService(_StaticLearningPath()).generate_contract_report("S-0001")
    dimensions = {item["id"]: item for item in report["radar"]["dimensions"]}

    assert dimensions["operation"]["score"] == 80.0
    assert dimensions["spatial"]["score"] == 60.0
    assert dimensions["application"]["score"] == 75.0
    assert dimensions["resilience"]["status"] == "ready"
    assert dimensions["resilience"]["score"] is not None
    assert report["mastery_overview"] == {
        "weak_count": 0, "developing_count": 1, "mastered_count": 2, "average_mastery": 76.7,
    }
    assert report["learning_path_summary"] == {"count": 1, "first_knowledge_id": "K004"}
    assert events[0][0] == "growth_report.generated"
    assert "student_answer" not in events[0][1]


def test_growth_report_does_not_score_resilience_from_one_behavior_type(tmp_path, monkeypatch):
    database = tmp_path / "growth-report-insufficient.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE knowledge_mastery (student_id TEXT, knowledge_id TEXT, master_level REAL, priority REAL, correct_count INTEGER, wrong_count INTEGER);
            CREATE TABLE answer_history (student_id TEXT, question_id TEXT, is_correct INTEGER, error_tags TEXT, submitted_at TEXT);
            CREATE TABLE question_knowledge_mapping (question_id TEXT, knowledge_id TEXT);
            CREATE TABLE mistake_case (student_id TEXT, current_status TEXT);
            CREATE TABLE review2_plan (student_id TEXT, status TEXT);
            CREATE TABLE review2_session (id TEXT, student_id TEXT);
            CREATE TABLE review2_attempt (session_id TEXT, submitted_at TEXT);
            INSERT INTO answer_history VALUES ('S001', 'Q1', 1, NULL, '2026-08-24T09:00:00');
            """
        )
    ability_mapping.ensure_ability_mapping_schema(database)
    monkeypatch.setattr(growth_report, "DATABASE_PATH", str(database))

    report = growth_report.GrowthReportContractService(_StaticLearningPath()).generate_contract_report("S001")
    resilience = next(item for item in report["radar"]["dimensions"] if item["id"] == "resilience")

    assert resilience["score"] is None
    assert resilience["status"] == "insufficient_data"


def test_growth_report_reloads_mastery_and_review_correction_facts(tmp_path, monkeypatch):
    database = tmp_path / "growth-report-refresh.db"
    now = datetime.now().isoformat()
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE knowledge_mastery (student_id TEXT, knowledge_id TEXT, master_level REAL, priority REAL, correct_count INTEGER, wrong_count INTEGER);
            CREATE TABLE answer_history (student_id TEXT, question_id TEXT, is_correct INTEGER, error_tags TEXT, submitted_at TEXT);
            CREATE TABLE question_knowledge_mapping (question_id TEXT, knowledge_id TEXT);
            CREATE TABLE mistake_case (student_id TEXT, current_status TEXT);
            CREATE TABLE review2_plan (student_id TEXT, status TEXT);
            CREATE TABLE review2_session (id TEXT, student_id TEXT);
            CREATE TABLE review2_attempt (session_id TEXT, question_id TEXT, submitted_at TEXT, correction_at TEXT, correction_is_correct INTEGER);
            INSERT INTO knowledge_mastery VALUES ('S001', 'K004', 0.4, 0, 1, 2);
            INSERT INTO review2_plan VALUES ('S001', 'completed');
            INSERT INTO review2_session VALUES ('RS1', 'S001');
            INSERT INTO review2_attempt VALUES ('RS1', 'Q1', '%s', NULL, NULL);
            """ % now
        )
    ability_mapping.ensure_ability_mapping_schema(database)
    monkeypatch.setattr(growth_report, "DATABASE_PATH", str(database))
    service = growth_report.GrowthReportContractService(_StaticLearningPath())

    before = service.generate_contract_report("S001")
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE knowledge_mastery SET master_level = 0.8 WHERE student_id = 'S001' AND knowledge_id = 'K004'")
        connection.execute("UPDATE review2_attempt SET correction_at = ?, correction_is_correct = 1 WHERE session_id = 'RS1'", (now,))

    after = service.generate_contract_report("S001")
    before_dimensions = {item["id"]: item for item in before["radar"]["dimensions"]}
    after_dimensions = {item["id"]: item for item in after["radar"]["dimensions"]}

    assert before_dimensions["operation"]["score"] == 40.0
    assert after_dimensions["operation"]["score"] == 80.0
    assert after_dimensions["resilience"]["score"] > before_dimensions["resilience"]["score"]


def test_growth_report_logs_unmapped_knowledge_for_mapping_governance(tmp_path, monkeypatch):
    database = tmp_path / "growth-report-mapping-gap.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE knowledge_mastery (student_id TEXT, knowledge_id TEXT, master_level REAL, priority REAL, correct_count INTEGER, wrong_count INTEGER)"
        )
        connection.execute("INSERT INTO knowledge_mastery VALUES ('S001', 'K999', 0.5, 0, 1, 1)")
    ability_mapping.ensure_ability_mapping_schema(database)
    events = []
    monkeypatch.setattr(growth_report, "DATABASE_PATH", str(database))
    monkeypatch.setattr(growth_report, "log_event", lambda event, **fields: events.append((event, fields)))

    growth_report.GrowthReportContractService(_StaticLearningPath()).generate_contract_report("S001")

    assert ("growth_report.mapping_gap_detected", {
        "mapping_version": ability_mapping.MAPPING_VERSION,
        "missing_count": 1,
        "knowledge_ids": ["K999"],
    }) in events


def test_growth_report_uses_versioned_multi_dimension_mapping_weights(tmp_path, monkeypatch):
    database = tmp_path / "growth-report-mapping-weights.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE knowledge_mastery (student_id TEXT, knowledge_id TEXT, master_level REAL, priority REAL, correct_count INTEGER, wrong_count INTEGER);
            INSERT INTO knowledge_mastery VALUES ('S001', 'K004', 0.2, 0, 1, 3);
            INSERT INTO knowledge_mastery VALUES ('S001', 'K900', 0.8, 0, 4, 1);
            """
        )
    ability_mapping.ensure_ability_mapping_schema(database)
    with sqlite3.connect(database) as connection:
        connection.executemany(
            """INSERT INTO knowledge_ability_mapping
               (knowledge_id, dimension, weight, mapping_version, source)
               VALUES (?, ?, ?, ?, 'test')""",
            [
                ("K900", "operation", 3.0, ability_mapping.MAPPING_VERSION),
                ("K900", "logic", 2.0, ability_mapping.MAPPING_VERSION),
                ("K900", "spatial", 1.0, "ability-map-v0"),
            ],
        )
    monkeypatch.setattr(growth_report, "DATABASE_PATH", str(database))

    report = growth_report.GrowthReportContractService(_StaticLearningPath()).generate_contract_report("S001")
    dimensions = {item["id"]: item for item in report["radar"]["dimensions"]}

    assert dimensions["operation"]["score"] == 65.0
    assert dimensions["logic"]["score"] == 80.0
    assert dimensions["spatial"]["score"] is None


def test_growth_report_validates_response_and_remains_read_only(tmp_path, monkeypatch):
    database = tmp_path / "growth-report-read-only.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE knowledge_mastery (student_id TEXT, knowledge_id TEXT, master_level REAL, priority REAL, correct_count INTEGER, wrong_count INTEGER);
            INSERT INTO knowledge_mastery VALUES ('S001', 'K004', 0.7, 0, 3, 1);
            """
        )
    ability_mapping.ensure_ability_mapping_schema(database)
    monkeypatch.setattr(growth_report, "DATABASE_PATH", str(database))
    service = growth_report.GrowthReportContractService(_StaticLearningPath())

    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT * FROM knowledge_mastery").fetchall()
        mapping_before = connection.execute("SELECT * FROM knowledge_ability_mapping").fetchall()
    report = service.generate_contract_report("S001")
    with sqlite3.connect(database) as connection:
        after = connection.execute("SELECT * FROM knowledge_mastery").fetchall()
        mapping_after = connection.execute("SELECT * FROM knowledge_ability_mapping").fetchall()

    validated = GrowthReportResponse.model_validate(report)
    assert validated.student_id == "S001"
    assert before == after
    assert mapping_before == mapping_after


def test_growth_report_degrades_when_sqlite_is_unavailable(monkeypatch):
    events = []

    def unavailable_connect(*_args, **_kwargs):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(growth_report.sqlite3, "connect", unavailable_connect)
    monkeypatch.setattr(growth_report, "log_event", lambda event, **fields: events.append((event, fields)))

    report = growth_report.GrowthReportContractService(_StaticLearningPath()).generate_contract_report("S001")

    assert all(item["status"] == "unavailable" for item in report["radar"]["dimensions"])
    assert report["empty_state"]
    assert events[0][1]["degradation_reasons"] == ["sqlite_unavailable"]
