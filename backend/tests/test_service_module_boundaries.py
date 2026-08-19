from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_gateway_is_an_application_composition_module() -> None:
    source = (REPOSITORY_ROOT / "backend" / "api_gateway" / "app.py").read_text(encoding="utf-8")

    assert "def submit_homework(" not in source
    assert "def call_ocr_service(" not in source
    assert "def call_analysis_service(" not in source
    assert "def prepare_judging_input(" not in source


def test_submission_router_delegates_to_submission_service() -> None:
    source = (REPOSITORY_ROOT / "backend" / "api_gateway" / "routers" / "submissions.py").read_text(
        encoding="utf-8"
    )

    assert "process_submission(" in source
    assert "@router.post(\"/api/v1/submit\"" in source


def test_submission_orchestrator_delegates_external_calls_to_module_clients() -> None:
    source = (REPOSITORY_ROOT / "backend" / "api_gateway" / "services" / "submission_service.py").read_text(
        encoding="utf-8"
    )

    assert "import requests" not in source
    assert "OCR_SERVICE_URL" not in source
    assert "def _call_" not in source


def test_gateway_keeps_non_submission_routes_after_refactor() -> None:
    from backend.api_gateway.app import app

    paths = set(app.openapi()["paths"])

    assert "/api/v1/teacher/homework_batch" in paths
    assert "/api/student/{student_id}/stats" in paths
    assert "/api/error/analyze" in paths
