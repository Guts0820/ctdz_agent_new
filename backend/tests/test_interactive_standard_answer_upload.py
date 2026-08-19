from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_manual_standard_answer_script_exists() -> None:
    script = REPOSITORY_ROOT / "tools" / "manual_checks" / "interactive_standard_answer_upload.py"

    assert script.exists()
    assert "standard_answers" in script.read_text(encoding="utf-8")
