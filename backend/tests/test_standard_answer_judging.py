import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_judge_compares_normalized_student_answer_with_knowledge_graph_standard_answer() -> None:
    from backend.services.analysis_service import main as analysis_service

    result = analysis_service.judge_against_standard_answer(
        question="学校买了24箱矿泉水，每箱有3瓶，一共买了多少瓶？",
        student_answer=" ７２ ",
        standard_answer="72",
    )

    assert result["judge_result"] == "correct"
    assert result["is_copy"] is False
    assert result["core_error_type"] == ""


def test_judge_marks_a_different_answer_as_wrong_without_using_question_specific_rules() -> None:
    from backend.services.analysis_service import main as analysis_service

    result = analysis_service.judge_against_standard_answer(
        question="任意题目",
        student_answer="71",
        standard_answer="72",
    )

    assert result["judge_result"] == "wrong"
    assert result["core_error_type"] == "答案不一致"


def test_judge_uses_llm_result_and_passes_standard_steps(monkeypatch) -> None:
    from backend.services.analysis_service import main as analysis_service

    captured = {}

    def fake_judge_with_llm(**kwargs):
        captured.update(kwargs)
        return {
            "judge_result": "correct",
            "step_feedback": "结果正确，虽然解题步骤不同，但与标准答案等价。",
            "error_step_list": [],
            "miss_step_list": [],
            "core_error_type": "",
            "confidence": 0.98,
        }

    monkeypatch.setattr(analysis_service, "judge_with_llm", fake_judge_with_llm)

    result = analysis_service.judge_against_standard_answer(
        question="计算 1/2 + 1/2",
        student_answer="1",
        standard_answer="2/2=1",
        standard_solve_steps="先通分，再相加，最后约分为 1。",
    )

    assert result["judge_result"] == "correct"
    assert result["confidence"] == 0.98
    assert captured["standard_solve_steps"] == "先通分，再相加，最后约分为 1。"


def test_invalid_llm_result_is_rejected_and_rule_judging_is_used(monkeypatch) -> None:
    from backend.services.analysis_service import main as analysis_service

    def invalid_judge_with_llm(**kwargs):
        return {
            "judge_result": "maybe",
            "step_feedback": "不确定",
            "confidence": 2.0,
        }

    monkeypatch.setattr(analysis_service, "judge_with_llm", invalid_judge_with_llm)

    result = analysis_service.judge_against_standard_answer(
        question="任意题目",
        student_answer="71",
        standard_answer="72",
    )

    assert result["judge_result"] == "wrong"
    assert result["core_error_type"] == "答案不一致"
