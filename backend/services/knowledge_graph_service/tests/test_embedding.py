from pathlib import Path
import sys


KG_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KG_SERVICE_DIR))


def test_qwen_embedding_client_uses_configured_model_and_dimensions(monkeypatch) -> None:
    from embedding import QwenEmbeddingClient

    calls = {}

    class FakeEmbeddings:
        def create(self, **kwargs):
            calls.update(kwargs)
            return type("Response", (), {
                "data": [type("Item", (), {"index": 0, "embedding": [0.1, 0.2]})()]
            })()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls.update(client=kwargs)
            self.embeddings = FakeEmbeddings()

    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("QWEN_EMBEDDING_MODEL", "text-embedding-v3")
    monkeypatch.setenv("QWEN_EMBEDDING_DIMENSIONS", "2")
    monkeypatch.setattr("embedding.OpenAI", FakeOpenAI)

    result = QwenEmbeddingClient().embed_texts(["题目文本"])

    assert result == [[0.1, 0.2]]
    assert calls["model"] == "text-embedding-v3"
    assert calls["dimensions"] == 2
    assert calls["input"] == ["题目文本"]
    assert calls["client"]["http_client"]._trust_env is False
    calls["client"]["http_client"].close()


def test_vector_candidate_search_calls_neo4j_vector_index(monkeypatch) -> None:
    from routers import questions

    monkeypatch.setattr(questions, "embed_query_text", lambda text: [0.1, 0.2])
    captured = {}

    def fake_query(query, parameters):
        captured.update(query=query, parameters=parameters)
        return [{"node": {"id": "Q1", "text": "1+1=", "answer": "2"}, "score": 0.91}]

    monkeypatch.setattr(questions.neo4j_conn, "query", fake_query)

    candidates = questions.search_vector_candidates("1+1=", limit=3)

    assert candidates[0]["id"] == "Q1"
    assert candidates[0]["retrieval_score"] == 0.91
    assert "db.index.vector.queryNodes" in captured["query"]
    assert captured["parameters"]["embedding"] == [0.1, 0.2]


def test_image2_import_query_writes_embedding_property() -> None:
    from tools.import_image2_questions import build_upsert_query

    assert "q.embedding = item.embedding" in build_upsert_query()
