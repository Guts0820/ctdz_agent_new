from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_backend_utility_scripts_are_grouped_by_purpose() -> None:
    expected_scripts = [
        REPOSITORY_ROOT / "backend" / "tools" / "diagnostics" / "check_mistakes.py",
        REPOSITORY_ROOT / "backend" / "tools" / "diagnostics" / "check_tables.py",
        REPOSITORY_ROOT / "backend" / "tools" / "manual_checks" / "batch_direct_check.py",
        REPOSITORY_ROOT / "backend" / "tools" / "manual_checks" / "batch_simple_check.py",
        REPOSITORY_ROOT / "backend" / "tools" / "manual_checks" / "batch_validation_check.py",
    ]

    assert all(path.is_file() for path in expected_scripts)
