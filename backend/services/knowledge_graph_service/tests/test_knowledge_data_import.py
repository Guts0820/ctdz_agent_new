from pathlib import Path
import sys


KG_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KG_SERVICE_DIR))


def test_load_knowledge_points_merges_explanations() -> None:
    from tools.import_knowledge_data import load_knowledge_points

    items = load_knowledge_points()

    assert len(items) == 255
    first = next(item for item in items if item["id"] == "K001")
    assert first["title"]
    assert first["content"]
    assert first["common_mistakes"]
    assert first["teaching_points"]


def test_load_error_causes_reads_reviewed_reference_asset() -> None:
    from tools.import_knowledge_data import load_error_causes

    items = load_error_causes()

    assert len(items) >= 17
    first = next(item for item in items if item["id"] == "C-001")
    assert first["level1"] == "计算"
    assert first["criteria"]
    assert first["knowledge_scope"]
    assert first["example"]
