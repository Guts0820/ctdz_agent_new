"""Send one local photo to OCR using the same multipart field as the frontend."""

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import requests


DEFAULT_OCR_URL = "http://127.0.0.1:8089/v1/recognize"
CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def recognize_frontend_upload(
    image_path: Path, ocr_url: str = DEFAULT_OCR_URL, timeout_seconds: int = 600
) -> dict[str, Any]:
    """Upload a photo as ``FormData.append('image', file)`` does in the frontend."""
    if not image_path.is_file():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    content_type = CONTENT_TYPES.get(image_path.suffix.lower())
    if not content_type:
        supported = ", ".join(sorted(CONTENT_TYPES))
        raise ValueError(f"Unsupported image type: {image_path.suffix}. Supported: {supported}")

    with image_path.open("rb") as image_file:
        response = requests.post(
            ocr_url,
            files={"image": (image_path.name, image_file, content_type)},
            timeout=timeout_seconds,
        )
    response.raise_for_status()
    return response.json()


def run_interactive_upload_check(
    *,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    recognize_fn: Callable[[Path, str, int], dict[str, Any]] = recognize_frontend_upload,
    ocr_url: str = DEFAULT_OCR_URL,
    timeout_seconds: int = 600,
) -> int:
    """Keep accepting local photo paths until the user enters ``exit``."""
    while True:
        try:
            raw_path = input_fn("请输入图片路径（输入 exit 结束）：").strip()
        except EOFError:
            raw_path = "exit"

        if raw_path.lower() == "exit":
            print_fn("已退出 OCR 图片识别。")
            return 0
        if not raw_path:
            continue

        image_path = Path(raw_path.strip('"\''))
        try:
            result = recognize_fn(image_path, ocr_url, timeout_seconds)
        except (FileNotFoundError, ValueError, requests.RequestException) as error:
            print_fn(json.dumps({"error": str(error)}, ensure_ascii=False, indent=2))
            continue

        print_fn(json.dumps(result, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload one photo to the OCR service and print the recognition result."
    )
    parser.add_argument(
        "image",
        type=Path,
        nargs="?",
        help="Optional path to a JPG, PNG, WebP, or BMP photo; omit for interactive mode",
    )
    parser.add_argument("--url", default=DEFAULT_OCR_URL, help="OCR endpoint URL")
    parser.add_argument("--timeout", type=int, default=600, help="Request timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.image is None:
        return run_interactive_upload_check(
            ocr_url=args.url,
            timeout_seconds=args.timeout,
        )

    try:
        result = recognize_frontend_upload(args.image, args.url, args.timeout)
    except (FileNotFoundError, ValueError, requests.RequestException) as error:
        print(f"OCR check failed: {error}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
