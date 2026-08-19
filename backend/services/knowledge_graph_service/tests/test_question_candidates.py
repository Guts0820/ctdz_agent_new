from pathlib import Path
import sys


KG_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KG_SERVICE_DIR))


def test_candidate_search_ranks_the_same_question_despite_ocr_formatting_differences(
    monkeypatch,
) -> None:
    from routers import questions

    monkeypatch.setattr(questions, "search_vector_candidates", lambda text, limit: [])
    monkeypatch.setattr(
        questions.neo4j_conn,
        "query",
        lambda query, parameters: [
            {
                "q": {
                    "id": "Q0005",
                    "text": "有几名同学测视力？兰兰排第几？明明离开后，兰兰排第几，她前面还有几名同学？",
                    "answer": "5名；第4；第3；1名。",
                }
            },
            {
                "q": {
                    "id": "Q0006",
                    "text": "排队题：几名同学排第几。",
                    "answer": "第2。",
                }
            },
        ],
    )

    candidates = questions.search_question_candidates(
        "（1）有（ ）名同学测视力，兰兰排第（ ）。"
        "（2）明明离开后，兰兰排第（ ），她前面还有（ ）名同学。",
        limit=2,
    )

    assert candidates[0]["id"] == "Q0005"
    assert candidates[0]["retrieval_score"] > candidates[1]["retrieval_score"]
    assert candidates[0]["match_type"] == "hybrid_lexical"
