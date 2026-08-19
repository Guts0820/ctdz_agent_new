from app.schemas import validate_standard_answer_input


def test_standard_answer_schema_preserves_each_question_and_answer() -> None:
    content = """
    {
      "schema_version": "1.0",
      "questions": [
        {
          "question": {"text": "1+1=", "explanation": "求两个数的和。", "visual_context": []},
          "student_answer": {"text": "2"}
        },
        {
          "question": {"text": "2+2=", "explanation": "求两个数的和。", "visual_context": []},
          "student_answer": {"text": "4"}
        }
      ],
      "confidence": 0.99,
      "review_required": false
    }
    """

    result = validate_standard_answer_input(content)

    assert len(result["questions"]) == 2
    assert result["questions"][1]["student_answer"]["text"] == "4"


def test_standard_answer_schema_rejects_empty_question_list() -> None:
    content = '{"schema_version":"1.0","questions":[],"confidence":0.99,"review_required":false}'

    try:
        validate_standard_answer_input(content)
    except ValueError:
        return
    raise AssertionError("empty standard-answer question lists must be rejected")
