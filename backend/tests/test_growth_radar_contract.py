import sqlite3

from backend.services.review_service.datahub.core import ability_mapping, growth_report


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
        connection.execute("CREATE TABLE knowledge_mastery (student_id TEXT)")
        connection.execute("INSERT INTO knowledge_mastery VALUES ('S001')")
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
