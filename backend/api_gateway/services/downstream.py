"""统一执行网关下游调用并转换传输层错误。

每次调用都会打一条 ``submit.stage`` 事件（``stage`` / ``elapsed_ms`` / ``ok``，
失败时附 ``status_code``），压测脚本按时间窗口或 ``request_id`` 聚合出各阶段耗时占比。
"""

import time
from collections.abc import Callable
from typing import Any

import requests
from fastapi import HTTPException

from backend.shared.observability import elapsed_ms, log_event


def _response_detail(error: requests.HTTPError) -> str:
    if error.response is None:
        return ""
    try:
        return str(error.response.json().get("detail", ""))[:300]
    except (ValueError, AttributeError):
        return ""


def execute_downstream(stage: str, operation: Callable[[], Any]) -> Any:
    start = time.perf_counter()
    try:
        result = _invoke_downstream(stage, operation)
    except HTTPException as error:
        log_event(
            "submit.stage",
            stage=stage,
            elapsed_ms=elapsed_ms(start),
            ok=False,
            status_code=error.status_code,
        )
        raise
    log_event("submit.stage", stage=stage, elapsed_ms=elapsed_ms(start), ok=True)
    return result


def _invoke_downstream(stage: str, operation: Callable[[], Any]) -> Any:
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
