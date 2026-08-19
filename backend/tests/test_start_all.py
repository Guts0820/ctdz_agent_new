import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend import start_all


def test_service_environment_uses_the_declared_port(monkeypatch) -> None:
    monkeypatch.setenv("API_PORT", "8000")

    environment = start_all.build_service_environment(8007)

    assert environment["API_PORT"] == "8007"
    assert environment["PYTHONPATH"].split(os.pathsep)[0] == str(PROJECT_ROOT)


def test_start_service_uses_paths_anchored_to_the_project_root(monkeypatch, tmp_path: Path) -> None:
    captured = {}
    process = object()

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return process

    monkeypatch.setattr(start_all.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(start_all.time, "sleep", lambda _: None)

    result = start_all.start_service(
        "Example Service",
        "backend/tools/init_sqlite_database.py",
        8007,
        log_dir=tmp_path,
    )

    assert result is process
    assert captured["command"] == [
        sys.executable,
        str(PROJECT_ROOT / "backend" / "tools" / "init_sqlite_database.py"),
    ]
    assert captured["cwd"] == str(PROJECT_ROOT)
