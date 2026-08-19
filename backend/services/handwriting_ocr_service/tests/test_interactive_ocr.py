import json
from pathlib import Path

import pytest

from app.models import RecognitionResult
from interactive_ocr import (
    recognize_image_to_markdown,
    run_interactive,
    validate_image_path,
)


class FakeRecognitionService:
    def __init__(
        self,
        markdown: str,
        analysis_input: dict[str, object] | None = None,
    ) -> None:
        self.markdown = markdown
        self.analysis_input = analysis_input
        self.received: tuple[bytes, str] | None = None

    def recognize(self, image_bytes: bytes, content_type: str) -> RecognitionResult:
        self.received = (image_bytes, content_type)
        return RecognitionResult(
            markdown=self.markdown,
            confidence=0.95,
            engine="fake",
            fallback_used=False,
            status="success",
            blocks=({"type": "image", "text": "图片块"}, {"type": "text", "text": "题目块"}),
            analysis_input=self.analysis_input,
        )


def test_recognizes_an_absolute_image_path_and_writes_markdown(tmp_path: Path) -> None:
    image_path = tmp_path / "handwriting.jpg"
    image_path.write_bytes(b"image bytes")
    output_dir = tmp_path / "recognition_results"
    service = FakeRecognitionService("# 识别结果\n\n1 + 1 = 2\n")

    output_path = recognize_image_to_markdown(image_path, output_dir, service)

    assert output_path == output_dir / "handwriting.md"
    assert output_path.read_text(encoding="utf-8") == "# 识别结果\n\n1 + 1 = 2\n"
    assert service.received == (b"image bytes", "image/jpeg")


def test_preserves_an_existing_result_by_adding_a_numbered_suffix(tmp_path: Path) -> None:
    image_path = tmp_path / "exercise.png"
    image_path.write_bytes(b"new image")
    output_dir = tmp_path / "recognition_results"
    output_dir.mkdir()
    (output_dir / "exercise.md").write_text("existing", encoding="utf-8")
    service = FakeRecognitionService("new result")

    output_path = recognize_image_to_markdown(image_path, output_dir, service)

    assert output_path == output_dir / "exercise_2.md"
    assert (output_dir / "exercise.md").read_text(encoding="utf-8") == "existing"


def test_rejects_a_relative_image_path() -> None:
    with pytest.raises(ValueError, match="绝对路径"):
        validate_image_path("images/exercise.jpg")


def test_exit_creates_the_output_folder_without_loading_models(tmp_path: Path) -> None:
    output_dir = tmp_path / "recognition_results"
    messages: list[str] = []

    def unexpected_service_factory() -> FakeRecognitionService:
        raise AssertionError("exit should not load recognition models")

    run_interactive(
        input_fn=lambda _: "exit",
        print_fn=messages.append,
        output_dir=output_dir,
        service_factory=unexpected_service_factory,
    )

    assert output_dir.is_dir()
    assert any("已退出" in message for message in messages)


def test_interactive_mode_prints_the_validated_analysis_input_as_json(tmp_path: Path) -> None:
    image_path = tmp_path / "exercise.png"
    image_path.write_bytes(b"image bytes")
    analysis_input = {
        "schema_version": "1.0",
        "question": {"text": "1 + 1 = ?", "explanation": "计算加法", "visual_context": []},
        "student_answer": {"text": "2"},
        "confidence": 0.95,
        "review_required": False,
    }
    messages: list[str] = []
    inputs = iter([str(image_path), "exit"])

    run_interactive(
        input_fn=lambda _: next(inputs),
        print_fn=messages.append,
        output_dir=tmp_path / "recognition_results",
        service_factory=lambda: FakeRecognitionService("# 识别结果", analysis_input),
    )

    json_messages = [message for message in messages if message.startswith("{")]
    assert json.loads(json_messages[-1]) == analysis_input
