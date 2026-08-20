import requests
import pytest
from fastapi import HTTPException

from backend.api_gateway.models import SubmitRequest
from backend.api_gateway.services import submission_service as gateway


def analysis_result(judge_result="wrong"):
    return {
        "student_id": "S001", "question_id": "Q001", "knowledge_id": "K035",
        "original_question": "25+38等于多少？", "student_write": "53",
        "answer_history_id": "AH001", "judge_result": judge_result, "step_feedback": "检查进位", "error_step_list": ["十位"],
        "miss_step_list": ["进位1"], "is_copy": False, "core_error_type": "数值错误", "confidence": 0.9,
    }


def error_result(knowledge_id="K035"):
    return {
        "error_tags": [{"error_id": "C-001", "level1": "计算", "level2": "口算", "level3": "漏加进位", "confidence": 0.9}],
        "knowledge_id": knowledge_id, "knowledge_scope": "100以内进位加法", "reasoning_content": "遗漏进位",
        "total_confidence": 0.9, "low_confidence": False, "fallback_used": False, "mistake_case_id": "MC001",
    }


def install_common(monkeypatch, calls):
    monkeypatch.setattr(gateway, "fetch_question", lambda _qid: {"id": "Q001", "answer": "63", "answer_steps": ["进位"], "knowledge_id": "K035"})
    monkeypatch.setattr(gateway, "analyze_submission", lambda _payload: calls.append("analysis") or analysis_result())
    def analyze_error(payload):
        calls.append("error")
        assert payload["answer_history_id"] == "AH001"
        return error_result()
    monkeypatch.setattr(gateway, "analyze_error", analyze_error)
    monkeypatch.setattr(gateway, "retrieve_knowledge", lambda payload: calls.append("knowledge") or {
        "knowledge_explanation": "进位加法讲解", "difficulty": "medium", "standard_solution": "个位进位",
        "common_errors": "漏加进位", "teaching_tips": "标记进位",
    })
    monkeypatch.setattr(gateway, "check_frequency", lambda *_args: calls.append("frequency") or {"push_permission": True})
    monkeypatch.setattr(gateway, "update_state", lambda *_args: calls.append("state") or {
        "master_level": 0.3, "knowledge_mastery_id": "KM001", "should_generate_review": True,
        "mastery": 30.0, "priority": 72.5,
        "next_action": "basic_practice", "correct_count": 0, "wrong_count": 1, "mastery_status": "pending",
    })
    def teaching(payload):
        calls.append("teaching")
        assert payload["mistake_case_id"] == "MC001"
        assert payload["grade"] == "四年级"
        return {"explanation": "讲解", "guided_explanation": "引导", "final_answer_explanation": "完整答案", "hints": ["提示1", "提示2"], "practice_list": [], "teaching_mode": "BASIC", "fallback_used": True, "fallback_reason": "模板降级", "practice_fallback_reason": "题库为空"}
    monkeypatch.setattr(gateway, "generate_teaching", teaching)
    monkeypatch.setattr(gateway, "generate_review", lambda *_args: calls.append("review") or {"review_plan_id": "RP001", "status": "generated"})
    monkeypatch.setattr(gateway, "_is_answer_released", lambda _qid: True)


def test_wrong_answer_runs_full_pipeline_in_order(monkeypatch):
    calls = []
    install_common(monkeypatch, calls)
    response = gateway.process_submission(SubmitRequest(student_id="S001", question_id="Q001", original_question="25+38等于多少？", student_write="53", grade="四年级"))
    assert calls == ["analysis", "error", "knowledge", "frequency", "state", "teaching", "review"]
    assert response.status == "success"
    assert response.data["mistake_case_id"] == "MC001"
    assert response.data["fallback_used"] is True
    assert response.data["error_analysis_fallback_used"] is False
    assert response.data["teaching_fallback_used"] is True


def test_missing_knowledge_id_stops_before_knowledge_and_teaching(monkeypatch):
    calls = []
    install_common(monkeypatch, calls)
    monkeypatch.setattr(gateway, "fetch_question", lambda _qid: {"id": "Q001", "answer": "63", "answer_steps": ["进位"], "knowledge_id": ""})
    monkeypatch.setattr(gateway, "analyze_submission", lambda _payload: {**analysis_result(), "knowledge_id": None})
    monkeypatch.setattr(gateway, "analyze_error", lambda _payload: error_result(""))
    monkeypatch.setattr(gateway, "retrieve_knowledge", lambda _payload: pytest.fail("不应调用知识服务"))
    with pytest.raises(HTTPException) as caught:
        gateway.process_submission(SubmitRequest(student_id="S001", question_id="Q001", original_question="题目", student_write="53"))
    assert caught.value.status_code == 422


def test_downstream_unavailable_returns_503_without_false_success(monkeypatch):
    calls = []
    install_common(monkeypatch, calls)
    monkeypatch.setattr(gateway, "retrieve_knowledge", lambda _payload: (_ for _ in ()).throw(requests.ConnectionError()))
    with pytest.raises(HTTPException) as caught:
        gateway.process_submission(SubmitRequest(student_id="S001", question_id="Q001", original_question="题目", student_write="53"))
    assert caught.value.status_code == 503
    assert "知识服务" in caught.value.detail
    assert "state" not in calls


def test_invalid_knowledge_response_returns_502(monkeypatch):
    calls = []
    install_common(monkeypatch, calls)
    monkeypatch.setattr(gateway, "retrieve_knowledge", lambda _payload: {"knowledge_explanation": "字段不完整"})
    with pytest.raises(HTTPException) as caught:
        gateway.process_submission(SubmitRequest(student_id="S001", question_id="Q001", original_question="题目", student_write="53"))
    assert caught.value.status_code == 502


def test_missing_downstream_resource_returns_404(monkeypatch):
    calls = []
    install_common(monkeypatch, calls)
    response = requests.Response()
    response.status_code = 404
    response._content = b'{"detail":"knowledge missing"}'
    error = requests.HTTPError(response=response)
    monkeypatch.setattr(gateway, "retrieve_knowledge", lambda _payload: (_ for _ in ()).throw(error))
    with pytest.raises(HTTPException) as caught:
        gateway.process_submission(SubmitRequest(student_id="S001", question_id="Q001", original_question="题目", student_write="53"))
    assert caught.value.status_code == 404


def test_correct_answer_skips_error_knowledge_and_teaching(monkeypatch):
    calls = []
    install_common(monkeypatch, calls)
    monkeypatch.setattr(gateway, "analyze_submission", lambda _payload: calls.append("analysis") or analysis_result("correct"))
    response = gateway.process_submission(SubmitRequest(student_id="S001", question_id="Q001", original_question="题目", student_write="63"))
    assert calls == ["analysis", "state", "review"]
    assert response.data["judge_result"] == "correct"
    assert response.data["mastery"] == 30.0
    assert response.data["priority"] == 72.5
    assert response.data["review_plan"]["review_plan_id"] == "RP001"
