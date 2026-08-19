from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_analysis_service_contains_no_ocr_client_or_question_specific_judging_rules() -> None:
    source = (REPOSITORY_ROOT / "backend" / "services" / "analysis_service" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "def call_ocr_service(" not in source
    assert "def run_ocr(" not in source
    assert 'if "25" in question and "38" in question:' not in source
