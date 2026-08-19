import base64
from pathlib import Path

import pytest

from backend.tools.manual_checks.interactive_image_judging import (
    SubmissionError,
    encode_image_as_data_uri,
    format_submission_result,
    submit_image,
    validate_image_path,
)


def test_encode_image_as_data_uri_uses_the_image_content_type(tmp_path: Path) -> None:
    image_path = tmp_path / "question.png"
    image_path.write_bytes(b"image bytes")

    data_uri = encode_image_as_data_uri(image_path)

    assert data_uri == "data:image/png;base64," + base64.b64encode(b"image bytes").decode("ascii")


def test_submit_image_posts_to_gateway_with_image_only_payload(tmp_path: Path) -> None:
    image_path = tmp_path / "question.jpg"
    image_path.write_bytes(b"image bytes")
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"status": "success", "data": {"judge_result": "correct"}}

    def fake_post(url, *, json, timeout):
        captured.update({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    result = submit_image(
        image_path,
        gateway_url="http://localhost:8000",
        student_id="interactive-test",
        post=fake_post,
    )

    assert result["data"]["judge_result"] == "correct"
    assert captured["url"] == "http://localhost:8000/api/v1/submit"
    assert captured["json"]["student_id"] == "interactive-test"
    assert captured["json"]["image"].startswith("data:image/jpeg;base64,")


def test_submit_image_returns_the_gateway_detail_for_unknown_graph_question(tmp_path: Path) -> None:
    image_path = tmp_path / "question.jpg"
    image_path.write_bytes(b"image bytes")

    class FakeResponse:
        status_code = 422

        def json(self):
            return {"detail": "OCR 题干无法匹配知识图谱中的标准题目"}

    with pytest.raises(SubmissionError, match="OCR 题干无法匹配知识图谱中的标准题目"):
        submit_image(image_path, post=lambda *args, **kwargs: FakeResponse())


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"status": "success", "data": {"judge_result": "correct"}}, "正确"),
        ({"status": "success", "data": {"judge_result": "wrong"}}, "错误"),
        ({"status": "success", "data": {"judge_result": "unknown"}}, "无法判断"),
    ],
)
def test_format_submission_result_returns_the_judgment_only(response: dict, expected: str) -> None:
    assert format_submission_result(response) == expected


def test_validate_image_path_rejects_a_missing_file() -> None:
    with pytest.raises(ValueError, match="不存在"):
        validate_image_path(r"C:\missing\question.jpg")
