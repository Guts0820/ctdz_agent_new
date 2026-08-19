import json


def test_llm_tags_use_error_bank_hierarchy_and_clamped_confidence(monkeypatch):
    from backend.services.error_analysis_service import main as service

    monkeypatch.setattr(
        service,
        "fetch_candidate_errors",
        lambda: [
            {
                "error_id": "C-001",
                "level1": "计算",
                "level2": "口算与基本运算",
                "level3": "进位加法中十位漏加进位1",
            }
        ],
    )
    monkeypatch.setattr(
        service,
        "fetch_candidate_knowledge",
        lambda: [{"id": "K035", "title": "100以内进位加法"}],
    )
    monkeypatch.setattr(
        service,
        "call_llm",
        lambda *_args, **_kwargs: json.dumps(
            {
                "error_tags": [
                    {
                        "error_id": "C-001",
                        "level1": "模型乱填的分类",
                        "level2": "模型乱填的子类",
                        "level3": "模型乱填的标签",
                        "confidence": 1.8,
                    }
                ],
                "knowledge_id": "K035",
                "reasoning_content": "漏加进位。",
                "total_confidence": 1.5,
            },
            ensure_ascii=False,
        ),
    )

    request = service.ErrorAnalysisRequest(
        student_id="S-0001",
        original_question="25+38=？",
        student_write="53",
        judge_result="wrong",
        core_error_type="计算错误",
        step_feedback="十位漏加进位",
    )
    tags, knowledge, reasoning, confidence = service.analyze_error_with_llm(request)

    assert tags[0].level1 == "计算"
    assert tags[0].level2 == "口算与基本运算"
    assert tags[0].level3 == "进位加法中十位漏加进位1"
    assert tags[0].confidence == 1.0
    assert knowledge == {"id": "K035", "scope": "100以内进位加法"}
    assert reasoning == "漏加进位。"
    assert confidence == 1.0


def test_empty_tags_are_always_low_confidence():
    from backend.services.error_analysis_service import main as service

    assert service.aggregate_confidence([], 0.95) == 0.4
    response = service.analyze_error(
        service.ErrorAnalysisRequest(
            student_id="S-0001",
            original_question="题目",
            student_write="不会",
            judge_result="wrong",
            core_error_type="未知",
            step_feedback="",
        )
    )

    assert response.low_confidence is True
    assert response.fallback_used is True
    assert response.total_confidence == 0.2


def test_correct_answer_skips_error_analysis():
    from backend.services.error_analysis_service import main as service

    response = service.analyze_error(
        service.ErrorAnalysisRequest(
            student_id="S-0001",
            original_question="1+1=？",
            student_write="2",
            judge_result="correct",
            core_error_type="",
            step_feedback="",
        )
    )

    assert response.error_tags == []
    assert response.total_confidence == 1.0
    assert response.low_confidence is False
    assert response.fallback_used is False


def test_light_analysis_marks_low_confidence_when_llm_is_unavailable(monkeypatch):
    from backend.services.error_analysis_service import main as service

    monkeypatch.setattr(
        service,
        "analyze_error_with_llm_light",
        lambda _request: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    response = service.analyze_error_light(
        service.LightErrorAnalysisRequest(
            student_id="S-0001",
            original_question="25+38=？",
            correct_answer="63",
            student_write="53",
            knowledge_id="K035",
        )
    )

    assert response.low_confidence is True
    assert response.fallback_used is True
    assert response.total_confidence <= 0.6
