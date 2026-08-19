"""通过教师端上传标准答案图片并输出导入 Neo4j 的 JSON 结果。"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

import requests

# Allow direct execution as ``python backend/tools/manual_checks/...py``.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.tools.manual_checks.interactive_image_judging import validate_image_path


DEFAULT_GATEWAY_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 660.0


class StandardAnswerUploadError(RuntimeError):
    def __init__(self, detail: str, status_code: int | None = None) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


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


def upload_image(
    image_path: Path,
    *,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    validated_path = validate_image_path(str(image_path))
    content_type = {
        ".bmp": "image/bmp",
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }[validated_path.suffix.lower()]
    try:
        response = post(
            f"{gateway_url.rstrip('/')}/api/v1/teacher/standard_answers",
            files={"image": (validated_path.name, validated_path.read_bytes(), content_type)},
            timeout=timeout,
        )
    except requests.RequestException as error:
        raise StandardAnswerUploadError(f"无法连接后端接口：{error}") from error
    if response.status_code >= 400:
        raise StandardAnswerUploadError(_response_detail(response), response.status_code)
    try:
        body = response.json()
    except ValueError as error:
        raise StandardAnswerUploadError("后端返回的不是有效 JSON。", response.status_code) from error
    if not isinstance(body, dict):
        raise StandardAnswerUploadError("后端返回的 JSON 格式不正确。", response.status_code)
    return body


def run_interactive(
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    gateway_url: str | None = None,
) -> None:
    configured_gateway = gateway_url or os.getenv("API_GATEWAY_URL", DEFAULT_GATEWAY_URL)
    print_fn(f"标准答案上传接口：{configured_gateway.rstrip('/')}/api/v1/teacher/standard_answers")
    print_fn("请输入标准答案图片绝对路径；输入 exit 退出。")
    while True:
        try:
            raw_path = input_fn("图片路径> ")
        except (EOFError, KeyboardInterrupt):
            print_fn("\n已退出标准答案上传测试。")
            return
        if raw_path.strip().lower() == "exit":
            print_fn("已退出标准答案上传测试。")
            return
        try:
            result = upload_image(
                validate_image_path(raw_path),
                gateway_url=configured_gateway,
            )
            print_fn(json.dumps(result, ensure_ascii=False, indent=2))
        except (ValueError, StandardAnswerUploadError) as error:
            print_fn(json.dumps({"error": str(error)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_interactive()
