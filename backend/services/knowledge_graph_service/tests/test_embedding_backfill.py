from pathlib import Path
import sys


KG_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KG_SERVICE_DIR))


def test_backfill_query_updates_question_embedding() -> None:
    from tools.backfill_question_embeddings import build_backfill_query

    assert "SET q.embedding = item.embedding" in build_backfill_query()
