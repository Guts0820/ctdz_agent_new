"""统一执行网关下游调用并转换传输层错误。"""

from collections.abc import Callable
from typing import Any

import requests
from fastapi import HTTPException


def _response_detail(error: requests.HTTPError) -> str:
    if error.response is None:
        return ""
    try:
        return str(error.response.json().get("detail", ""))[:300]
    except (ValueError, AttributeError):
        return ""


def execute_downstream(stage: str, operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except HTTPException:
        raise
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else 503
        detail = _response_detail(error)
        if status == 404:
            raise HTTPException(status_code=404, detail=f"{stage}未找到所需数据：{detail or '资源不存在'}") from error
        if status in {400, 422}:
            raise HTTPException(status_code=422, detail=f"{stage}拒绝请求：{detail or '输入不满足处理条件'}") from error
        raise HTTPException(status_code=503, detail=f"{stage}暂不可用") from error
    except requests.exceptions.JSONDecodeError as error:
        raise HTTPException(status_code=502, detail=f"{stage}返回格式非法") from error
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail=f"{stage}暂不可用") from error
    except (ValueError, TypeError, KeyError) as error:
        raise HTTPException(status_code=502, detail=f"{stage}返回格式非法") from error


def require_fields(stage: str, payload: Any, fields: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict) or any(field not in payload for field in fields):
        raise HTTPException(status_code=502, detail=f"{stage}返回格式非法")
    return payload
