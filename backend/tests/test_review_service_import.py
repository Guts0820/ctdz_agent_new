import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_review_service_imports_from_the_backend_service_path() -> None:
    command = (
        "from backend.services.review_service import main as review_service; "
        "assert review_service.app.title == 'Review Service'"
    )

    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_review_service_exposes_merged_mastery_and_datahub_routes() -> None:
    from backend.services.review_service.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/mastery/student_overview/{student_id}" in paths
    assert "/api/datahub/growth_report/{student_id}" in paths
