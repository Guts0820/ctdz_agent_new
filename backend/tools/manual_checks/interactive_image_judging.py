"""通过 API Gateway 联调图片 OCR、知识图谱匹配和判题流程。"""

import base64
import mimetypes
import os
from pathlib import Path
import sys
from typing import Any, Callable

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.shared.http_client import configure_proxy_bypass


configure_proxy_bypass()


SUPPORTED_IMAGE_TYPES = {
    ".bmp": "image/bmp",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
DEFAULT_GATEWAY_URL = "http://127.0.0.1:8000"
DEFAULT_STUDENT_ID = "interactive-test-student"
DEFAULT_TIMEOUT_SECONDS = 600.0


class SubmissionError(RuntimeError):
    """Gateway rejected the submission or returned an invalid response."""

    def __init__(self, detail: str, status_code: int | None = None) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def validate_image_path(raw_path: str) -> Path:
    """Validate a local absolute image path, accepting copied quoted paths."""
    normalized = raw_path.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1].strip()
    if not normalized:
        raise ValueError("图片路径不能为空。")

    image_path = Path(normalized)
    if not image_path.is_absolute():
        raise ValueError("请输入图片的绝对路径。")
    if not image_path.is_file():
        raise ValueError("图片文件不存在或路径不是文件。")
    if image_path.suffix.lower() not in SUPPORTED_IMAGE_TYPES:
        supported = ", ".join(sorted(SUPPORTED_IMAGE_TYPES))
        raise ValueError(f"不支持该图片格式，支持的扩展名：{supported}。")
    return image_path


def encode_image_as_data_uri(image_path: Path) -> str:
    """Encode an image in memory for the gateway's image field."""
    validated_path = validate_image_path(str(image_path))
    content_type = SUPPORTED_IMAGE_TYPES[validated_path.suffix.lower()]
    encoded = base64.b64encode(validated_path.read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _response_detail(response: Any) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        detail = body.get("detail") or body.get("message")
        if detail:
            return str(detail)
    return f"接口返回 HTTP {response.status_code}。"


def submit_image(
    image_path: Path,
    *,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    student_id: str = DEFAULT_STUDENT_ID,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    """Submit one local image to the public gateway and return its JSON body."""
    payload = {
        "student_id": student_id,
        "image": encode_image_as_data_uri(image_path),
    }
    try:
        response = post(
            f"{gateway_url.rstrip('/')}/api/v1/submit",
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as error:
        raise SubmissionError(f"无法连接后端接口：{error}") from error

    if response.status_code >= 400:
        raise SubmissionError(_response_detail(response), response.status_code)
    try:
        body = response.json()
    except ValueError as error:
        raise SubmissionError("后端返回的不是有效 JSON。", response.status_code) from error
    if not isinstance(body, dict):
        raise SubmissionError("后端返回的 JSON 格式不正确。", response.status_code)
    return body


def format_submission_result(response: dict[str, Any]) -> str:
    """Return the concise terminal judgment from a successful gateway response."""
    data = response.get("data")
    if not isinstance(data, dict):
        return "无法判断"
    result = data.get("judge_result")
    return {
        "correct": "正确",
        "wrong": "错误",
    }.get(result, "无法判断")


def run_interactive(
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    gateway_url: str | None = None,
    student_id: str | None = None,
) -> None:
    """Read image paths until ``exit`` and print one judgment per submission."""
    configured_gateway = gateway_url or os.getenv("API_GATEWAY_URL", DEFAULT_GATEWAY_URL)
    configured_student = student_id or os.getenv("STUDENT_ID", DEFAULT_STUDENT_ID)
    print_fn(f"判题接口：{configured_gateway.rstrip('/')}/api/v1/submit")
    print_fn("请输入图片绝对路径；输入 exit 退出。")

    while True:
        try:
            raw_path = input_fn("图片路径> ")
        except (EOFError, KeyboardInterrupt):
            print_fn("\n已退出图片判题测试。")
            return
        if raw_path.strip().lower() == "exit":
            print_fn("已退出图片判题测试。")
            return

        try:
            response = submit_image(
                validate_image_path(raw_path),
                gateway_url=configured_gateway,
                student_id=configured_student,
            )
            print_fn(format_submission_result(response))
        except (ValueError, SubmissionError) as error:
            print_fn(str(error))


if __name__ == "__main__":
    run_interactive()
