def test_knowledge_scope_accepts_integer_graph_grade_for_chinese_request():
    from backend.services.knowledge_service.main import validate_scope

    assert validate_scope(
        type("Request", (), {"grade": "三年级"})(),
        {"grade": 3},
    ) is True


def test_knowledge_scope_rejects_a_higher_grade_than_requested():
    from backend.services.knowledge_service.main import validate_scope

    assert validate_scope(
        type("Request", (), {"grade": "三年级"})(),
        {"grade": 4},
    ) is False
