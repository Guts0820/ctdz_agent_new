import json
import sqlite3


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


def test_error_analysis_links_answer_history_and_mistake_case(monkeypatch, tmp_path):
    from backend.services.error_analysis_service import main as service

    database = tmp_path / "pipeline.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE question (question_id TEXT, question_description TEXT);
            CREATE TABLE answer_history (answer_history_id TEXT PRIMARY KEY, mistake_case_id TEXT, error_tags TEXT, reasoning_content TEXT);
            CREATE TABLE mistake_case (mistake_case_id TEXT PRIMARY KEY, student_id TEXT, question_id TEXT, current_status TEXT, created_at TEXT);
            CREATE TABLE mistake_case_error (mistake_case_id TEXT, error_id TEXT, error_weight REAL);
            CREATE TABLE mistake_case_knowledge (mistake_case_id TEXT, knowledge_id TEXT, knowledge_weight REAL);
            INSERT INTO answer_history (answer_history_id) VALUES ('AH001');
            """
        )
    monkeypatch.setattr(service, "DATABASE", str(database))
    tag = service.ErrorTag(error_id="C-001", level1="计算", level2="口算", level3="漏加进位", confidence=0.9)
    monkeypatch.setattr(service, "analyze_error_with_llm", lambda _request: ([tag], {"id": "K035", "scope": "进位加法"}, "遗漏进位", 0.9))

    response = service.analyze_error(service.ErrorAnalysisRequest(
        student_id="S001", question_id="Q001", answer_history_id="AH001", original_question="25+38",
        student_write="53", judge_result="wrong", core_error_type="计算错误", step_feedback="漏加进位",
    ))

    with sqlite3.connect(database) as connection:
        history = connection.execute("SELECT mistake_case_id, error_tags, reasoning_content FROM answer_history WHERE answer_history_id='AH001'").fetchone()
        teaching_link = connection.execute("SELECT knowledge_id FROM mistake_case_knowledge WHERE mistake_case_id=?", (response.mistake_case_id,)).fetchone()
    assert history[0] == response.mistake_case_id
    assert json.loads(history[1])[0]["error_id"] == "C-001"
    assert history[2] == "遗漏进位"
    assert teaching_link[0] == "K035"
