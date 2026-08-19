from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_teacher_service_has_independent_fastapi_entrypoint() -> None:
    service_main = REPOSITORY_ROOT / "services" / "teacher_service" / "main.py"

    assert service_main.exists()
    assert "FastAPI" in service_main.read_text(encoding="utf-8")


def test_gateway_teacher_router_delegates_to_teacher_client() -> None:
    source = (REPOSITORY_ROOT / "api_gateway" / "routers" / "homework_batches.py").read_text(
        encoding="utf-8"
    )

    assert "teacher_client" in source
    assert "homework_batch_service" not in source


def test_gateway_does_not_keep_teacher_batch_database_logic() -> None:
    service_file = REPOSITORY_ROOT / "api_gateway" / "services" / "homework_batch_service.py"

    assert not service_file.exists()


def test_teacher_service_owns_batch_database_operations() -> None:
    source = (
        REPOSITORY_ROOT / "services" / "teacher_service" / "homework_batch_service.py"
    ).read_text(encoding="utf-8")

    assert "homework_batch" in source
    assert "homework_batch_question" in source
