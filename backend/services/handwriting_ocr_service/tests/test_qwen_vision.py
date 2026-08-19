import json

import pytest

from app.config import Settings
from app.services.qwen_vision import QwenVisionEngine


def _qwen_settings(monkeypatch) -> Settings:
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("QWEN_MODEL", "qwen-3.7plus")
    monkeypatch.setenv("QWEN_BASE_URL", "https://example.test/v1")
    return Settings.from_env()


def test_qwen_vision_returns_schema_validated_judging_input(monkeypatch) -> None:
    settings = _qwen_settings(monkeypatch)
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "schema_version": "1.0",
                                    "question": {
                                        "text": "图中长方形的面积是多少？",
                                        "explanation": "已知长和宽，计算面积。",
                                        "visual_context": [
                                            {"kind": "diagram", "description": "标注长和宽的长方形"}
                                        ],
                                    },
                                    "student_answer": {"text": "6×4=24"},
                                    "confidence": 0.94,
                                    "review_required": False,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("app.services.qwen_vision.requests.post", fake_post)

    result = QwenVisionEngine(settings).recognize(b"image", "image/png")

    assert result.engine == "qwen-3.7plus"
    assert result.structured_result == {
        "schema_version": "1.0",
        "question": {
            "text": "图中长方形的面积是多少？",
            "explanation": "已知长和宽，计算面积。",
            "visual_context": [{"kind": "diagram", "description": "标注长和宽的长方形"}],
        },
        "student_answer": {"text": "6×4=24"},
        "confidence": 0.94,
        "review_required": False,
    }
    assert captured["payload"]["model"] == "qwen-3.7plus"
    instruction = captured["payload"]["messages"][1]["content"][1]["text"]
    assert "涂改" in instruction
    assert "student_answer.text" in instruction
    assert "review_required=true" in instruction
    assert "题干与笔记分离" in instruction
    assert "批注" in instruction
    assert "不得用笔记中的数字补全或重建题干" in instruction


def test_qwen_vision_rejects_content_that_does_not_match_the_json_schema(monkeypatch) -> None:
    settings = _qwen_settings(monkeypatch)

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": '{"question": {}}'}}]}

    monkeypatch.setattr("app.services.qwen_vision.requests.post", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(ValueError, match="JSON Schema"):
        QwenVisionEngine(settings).recognize(b"image", "image/png")


def test_qwen_vision_standard_answer_mode_returns_separate_questions(monkeypatch) -> None:
    settings = _qwen_settings(monkeypatch)

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [{"message": {"content": json.dumps({
                    "schema_version": "1.0",
                    "questions": [
                        {
                            "question": {"text": "1+1=", "explanation": "求和。", "visual_context": []},
                            "student_answer": {"text": "2"},
                        },
                        {
                            "question": {"text": "2+2=", "explanation": "求和。", "visual_context": []},
                            "student_answer": {"text": "4"},
                        },
                    ],
                    "confidence": 0.99,
                    "review_required": False,
                }, ensure_ascii=False)}}]
            }

    monkeypatch.setattr("app.services.qwen_vision.requests.post", lambda *args, **kwargs: FakeResponse())

    result = QwenVisionEngine(settings).recognize(b"image", "image/png", mode="standard_answer")

    assert len(result.structured_result["questions"]) == 2
    assert result.structured_result["questions"][1]["student_answer"]["text"] == "4"
