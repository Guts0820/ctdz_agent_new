from pathlib import Path
import sys


KG_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KG_SERVICE_DIR))


def test_image2_import_uses_question_id_as_an_idempotent_merge_key() -> None:
    from tools.import_image2_questions import build_upsert_query

    query = build_upsert_query()

    assert "MERGE (q:Question {id: item.id})" in query
    assert "q.answer = item.answer" in query
    assert "q.source = item.source" in query
    assert "q.aliases = item.aliases" in query
