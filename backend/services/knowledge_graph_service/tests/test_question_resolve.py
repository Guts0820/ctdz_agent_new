from pathlib import Path
import sys


KG_SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KG_SERVICE_DIR))


def test_resolve_question_by_text_returns_the_graph_question_with_its_standard_answer(
    monkeypatch,
) -> None:
    from routers import questions

    monkeypatch.setattr(
        questions.neo4j_conn,
        "query",
        lambda query, parameters: [
            {
                "q": {
                    "id": "Q-0005",
                    "text": "学校买了24箱矿泉水，每箱有3瓶，一共买了多少瓶？",
                    "answer": "72",
                    "answer_steps": "24×3=72",
                }
            }
        ],
    )

    question = questions.resolve_question_by_text(
        "学校买了24箱矿泉水，每箱有3瓶，一共买了多少瓶？"
    )

    assert question.id == "Q-0005"
    assert question.answer == "72"
