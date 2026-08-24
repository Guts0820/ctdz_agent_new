def test_analysis_accepts_a_high_confidence_llm_reranked_graph_candidate(monkeypatch) -> None:
    from backend.services.analysis_service import question_retrieval

    candidate = {
        "id": "Q0005",
        "text": "有几名同学测视力？兰兰排第几？明明离开后，兰兰排第几，她前面还有几名同学？",
        "answer": "5名；第4；第3；1名。",
        "answer_steps": "兰兰原来第4，明明离开后前移一位。",
        "knowledge_id": "G-N-1-001",
        "retrieval_score": 0.71,
    }
    monkeypatch.setattr(question_retrieval, "retrieve_question_candidates", lambda text: [candidate])
    monkeypatch.setattr(
        question_retrieval,
        "rerank_question_candidates",
        lambda **kwargs: {
            "question_id": "Q0005",
            "confidence": 0.98,
            "runner_up_confidence": 0.02,
            "reason": "题干人物、场景和两问结构一致。",
        },
    )

    match = question_retrieval.resolve_question_reference("OCR 识别出的测视力排队题")

    assert match is not None
    assert match["question"]["id"] == "Q0005"
    assert match["match_confidence"] == 0.98


def test_analysis_accepts_normalized_exact_candidate_without_llm_rerank(monkeypatch) -> None:
    from backend.services.analysis_service import question_retrieval

    candidate = {
        "id": "TQ0911EFCEE4F0",
        "text": "0.8 × 0.02 =",
        "answer": "0.016",
        "answer_steps": "8×2=16，小数点共三位。",
        "match_type": "vector",
        "retrieval_score": 1.0,
    }
    monkeypatch.setattr(question_retrieval, "retrieve_question_candidates", lambda text: [candidate])

    monkeypatch.setattr(
        question_retrieval,
        "rerank_question_candidates",
        lambda **_kwargs: {
            "question_id": None,
            "confidence": 0.0,
            "runner_up_confidence": 0.0,
            "reason": "LLM无法判断",
        },
    )
    match = question_retrieval.resolve_question_reference("０．８×０．０２＝")

    assert match is not None
    assert match["question_id"] == "TQ0911EFCEE4F0"
    assert match["match_confidence"] == 1.0


def test_analysis_rejects_an_ambiguous_reranked_candidate(monkeypatch) -> None:
    from backend.services.analysis_service import question_retrieval

    candidates = [
        {"id": "Q0005", "text": "候选题一", "answer": "1", "retrieval_score": 0.71},
        {"id": "Q0006", "text": "候选题二", "answer": "2", "retrieval_score": 0.70},
    ]
    monkeypatch.setattr(question_retrieval, "retrieve_question_candidates", lambda text: candidates)
    monkeypatch.setattr(
        question_retrieval,
        "rerank_question_candidates",
        lambda **kwargs: {
            "question_id": "Q0005",
            "confidence": 0.94,
            "runner_up_confidence": 0.90,
            "reason": "两个候选题相近。",
        },
    )

    assert question_retrieval.resolve_question_reference("模糊题干") is None


def test_process_analysis_retrieves_a_graph_answer_before_judging(monkeypatch) -> None:
    from backend.services.analysis_service import main as analysis_service

    captured = {}

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, values):
            captured["history_values"] = values

        def commit(self):
            captured["committed"] = True

    monkeypatch.setattr(
        analysis_service,
        "resolve_question_reference",
        lambda text: {
            "question_id": "Q0005",
            "knowledge_id": "G-N-1-001",
            "match_confidence": 0.98,
            "match_reason": "人物与题干结构一致。",
            "question": {
                "id": "Q0005",
                "answer": "5名；第4；第3；1名。",
                "answer_steps": "明明离开后兰兰前移一位。",
            },
        },
    )
    monkeypatch.setattr(analysis_service, "get_db", lambda: FakeConnection())

    def fake_judge(**kwargs):
        captured["judge_input"] = kwargs
        return {
            "judge_result": "correct",
            "step_feedback": "答案正确。",
            "error_step_list": [],
            "miss_step_list": [],
            "is_copy": False,
            "core_error_type": "",
            "confidence": 0.99,
            "original_question": kwargs["question"],
            "student_write": kwargs["student_answer"],
            "text_status": "normal",
        }

    monkeypatch.setattr(analysis_service, "judge_against_standard_answer", fake_judge)

    response = analysis_service.process_analysis(
        analysis_service.AnalysisRequest(
            student_id="S-0001",
            original_question="OCR 识别的排队测视力题",
            student_write="5，4，3，1",
        )
    )

    assert captured["judge_input"]["standard_answer"] == "5名；第4；第3；1名。"
    assert response.question_id == "Q0005"
    assert response.question_match_confidence == 0.98
    assert captured["history_values"][2] == "Q0005"
    assert captured["committed"] is True


def test_process_analysis_rejects_unknown_question_without_writing_or_solving(monkeypatch) -> None:
    from backend.services.analysis_service import main as analysis_service
    monkeypatch.setattr(analysis_service, "resolve_question_reference", lambda text: None)
    def unexpected_solve(**_kwargs):
        raise AssertionError("student unknown-question path must not call solve LLM")
    monkeypatch.setattr(analysis_service, "judge_unseen_question_with_llm", unexpected_solve)
    with pytest.raises(analysis_service.HTTPException) as error:
        analysis_service.process_analysis(analysis_service.AnalysisRequest(
            student_id="S-0001", original_question="图谱中不存在的题目", student_write="72"
        ))
    assert error.value.status_code == 422
    assert error.value.detail == "题目不在题库中"


def test_process_analysis_returns_service_error_when_question_retrieval_is_down(monkeypatch) -> None:
    from backend.services.analysis_service import main as analysis_service
    monkeypatch.setattr(
        analysis_service,
        "resolve_question_reference",
        lambda _text: (_ for _ in ()).throw(ConnectionError("neo4j down")),
    )
    with pytest.raises(analysis_service.HTTPException) as error:
        analysis_service.process_analysis(analysis_service.AnalysisRequest(
            student_id="S-0001", original_question="0.8×0.02=", student_write="0.016"
        ))
    assert error.value.status_code == 503
import pytest
