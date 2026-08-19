from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_project_uses_separate_frontend_backend_and_database_roots() -> None:
    assert (PROJECT_ROOT / "frontend" / "index.html").is_file()
    assert (PROJECT_ROOT / "backend" / "api_gateway" / "app.py").is_file()
    assert (PROJECT_ROOT / "database" / "sqlite" / "example_db.db").is_file()
    assert (PROJECT_ROOT / "database" / "knowledge_graph" / "image2_questions.json").is_file()


def test_backend_services_have_explicit_module_directories() -> None:
    service_names = {
        "analysis_service",
        "error_analysis_service",
        "knowledge_service",
        "teaching_service",
        "state_service",
        "review_service",
        "knowledge_graph_service",
        "handwriting_ocr_service",
    }

    for service_name in service_names:
        service_root = PROJECT_ROOT / "backend" / "services" / service_name
        assert (service_root / "AGENTS.md").is_file(), service_name
        assert (service_root / "docs" / "README.md").is_file(), service_name


def test_legacy_top_level_module_directories_are_removed() -> None:
    for legacy_name in ("app_v2", "handwriting_ocr_service", "kg_service", "Review2.0"):
        assert not (PROJECT_ROOT / legacy_name).exists(), legacy_name
