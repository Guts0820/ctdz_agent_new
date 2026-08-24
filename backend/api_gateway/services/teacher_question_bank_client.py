from typing import Any
from urllib.parse import urlencode

from backend.api_gateway.services.teacher_client import _request


def list_teacher_questions(
    *,
    teacher_id: str,
    grade: int | None,
    semester: str | None,
    page: int,
    page_size: int,
    keyword: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"teacher_id": teacher_id, "page": page, "page_size": page_size}
    if grade is not None:
        params["grade"] = grade
    if semester:
        params["semester"] = semester
    if keyword:
        params["keyword"] = keyword
    return _request("GET", "/internal/api/v1/teacher/questions?" + urlencode(params))
