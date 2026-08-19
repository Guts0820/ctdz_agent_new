import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANUAL_CHECKS_DIR = REPOSITORY_ROOT / "backend" / "tools" / "manual_checks"


def test_upload_check_sends_a_photo_as_the_frontend_multipart_field(
    monkeypatch, tmp_path: Path
) -> None:
    sys.path.insert(0, str(MANUAL_CHECKS_DIR))
    import ocr_frontend_upload_check

    image_path = tmp_path / "homework.png"
    image_path.write_bytes(b"photo-bytes")
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"markdown": "1 + 1 = 2", "engine": "test-ocr"}

    def fake_post(url, *, files, timeout):
        filename, image_file, content_type = files["image"]
        captured.update(
            url=url,
            filename=filename,
            content_type=content_type,
            image_bytes=image_file.read(),
            timeout=timeout,
        )
        return FakeResponse()

    monkeypatch.setattr(ocr_frontend_upload_check.requests, "post", fake_post)

    result = ocr_frontend_upload_check.recognize_frontend_upload(
        image_path, "http://127.0.0.1:8089/v1/recognize", timeout_seconds=30
    )

    assert result == {"markdown": "1 + 1 = 2", "engine": "test-ocr"}
    assert captured == {
        "url": "http://127.0.0.1:8089/v1/recognize",
        "filename": "homework.png",
        "content_type": "image/png",
        "image_bytes": b"photo-bytes",
        "timeout": 30,
    }


def test_upload_check_rejects_unsupported_photo_extension(tmp_path: Path) -> None:
    sys.path.insert(0, str(MANUAL_CHECKS_DIR))
    import ocr_frontend_upload_check

    image_path = tmp_path / "homework.gif"
    image_path.write_bytes(b"photo-bytes")

    try:
        ocr_frontend_upload_check.recognize_frontend_upload(image_path, "http://example.test")
    except ValueError as error:
        assert "Unsupported image type" in str(error)
    else:
        raise AssertionError("unsupported image types must be rejected")


def test_interactive_upload_accepts_a_quoted_path_prints_json_and_exits() -> None:
    sys.path.insert(0, str(MANUAL_CHECKS_DIR))
    import ocr_frontend_upload_check

    responses = iter(['"C:\\photos\\homework.jpg"', "exit"])
    printed = []
    captured = []

    def fake_input(_: str) -> str:
        return next(responses)

    def fake_recognize(image_path: Path, ocr_url: str, timeout_seconds: int) -> dict[str, object]:
        captured.append((image_path, ocr_url, timeout_seconds))
        return {"markdown": "6 + 7 = 13", "engine": "test-ocr"}

    exit_code = ocr_frontend_upload_check.run_interactive_upload_check(
        input_fn=fake_input,
        print_fn=printed.append,
        recognize_fn=fake_recognize,
    )

    assert exit_code == 0
    assert captured == [
        (Path(r"C:\photos\homework.jpg"), "http://127.0.0.1:8089/v1/recognize", 600)
    ]
    assert json.loads(printed[0]) == {"markdown": "6 + 7 = 13", "engine": "test-ocr"}
    assert printed[-1] == "已退出 OCR 图片识别。"
