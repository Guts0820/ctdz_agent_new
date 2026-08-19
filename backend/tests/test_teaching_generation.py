import pytest
from pydantic import ValidationError

from backend.services.teaching_service import main as teaching


def make_request(master_level: float) -> teaching.TeachingGenerateRequest:
    return teaching.TeachingGenerateRequest(
        error_tags=[teaching.ErrorTag(error_id="C-001", level1="计算", level2="口算与基本运算", level3="进位加法中十位漏加进位1", confidence=0.9)],
        knowledge_scope="100以内进位加法", knowledge_id="K035", master_level=master_level,
        original_question="25+38等于多少？", student_write="53", grade="三年级",
    )


@pytest.mark.parametrize("value,expected", [(0, "BASIC"), (0.39, "BASIC"), (0.4, "STANDARD"), (0.8, "STANDARD"), (0.81, "ADVANCED"), (1, "ADVANCED")])
def test_teaching_mode_boundaries(value, expected):
    assert teaching.select_teaching_mode(value) == expected


def test_llm_content_rejects_direct_answer_and_invalid_hint_count():
    with pytest.raises(ValidationError):
        teaching.LLMTeachingContent(guided_explanation="答案是63。", final_answer_explanation="答案是63。", hints=["提示"], reasoning_content="依据")


@pytest.mark.parametrize("value,mode,difficulty,hint_count", [(0.2, "BASIC", "easy", 3), (0.6, "STANDARD", "medium", 2), (0.9, "ADVANCED", "hard", 2)])
def test_generate_teaching_fallback_is_traceable(monkeypatch, value, mode, difficulty, hint_count):
    requested = {}
    monkeypatch.setattr(teaching, "generate_teaching_with_llm", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))
    def empty(knowledge_id, difficulty, count=2):
        requested.update(knowledge_id=knowledge_id, difficulty=difficulty, count=count)
        return [], "题库为空"
    monkeypatch.setattr(teaching, "fetch_practice_questions", empty)
    monkeypatch.setattr(teaching, "save_teaching_content", lambda *_args: None)
    result = teaching.generate_teaching(make_request(value))
    assert result.teaching_mode == mode
    assert result.fallback_used is True
    assert result.practice_list == []
    assert result.practice_fallback_reason == "题库为空"
    assert requested == {"knowledge_id": "K035", "difficulty": difficulty, "count": 2}
    assert len(result.hints) == hint_count
    assert "答案是63" not in result.guided_explanation


def test_practice_candidates_without_verified_solution_are_filtered():
    result = teaching.build_practice_list([
        {"id": "Q1", "text": "18+25等于多少？", "answer": "43", "answer_steps": ["8+5=13", "1+2+1=4"]},
        {"id": "Q2", "text": "无解析题", "answer": "1", "answer_steps": ""},
    ], "easy")
    assert len(result) == 1
    assert result[0].solution == "8+5=13\n1+2+1=4"
