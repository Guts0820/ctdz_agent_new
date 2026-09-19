import json
import logging
import time
from contextvars import ContextVar
from functools import wraps
from typing import Callable, Any, Dict
from uuid import uuid4

from backend.shared.config import SERVICE_HEALTH_TIMEOUT_SECONDS


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


logger = logging.getLogger("ctdz_backend")


_current_request_id: ContextVar[Any] = ContextVar("ctdz_request_id", default=None)


def request_context() -> Dict[str, str]:
    return {"request_id": uuid4().hex}


def set_request_id(request_id: str) -> str:
    """Attach the caller-supplied request id so every later event can be correlated."""
    _current_request_id.set(request_id)
    return request_id


def get_request_id() -> Any:
    return _current_request_id.get()


def log_event(event: str, **fields: Any) -> None:
    request_id = get_request_id()
    payload = {
        "event": event,
        **({"request_id": request_id} if request_id else {}),
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


def elapsed_ms(start: float) -> float:
    """Milliseconds since a ``time.perf_counter()`` stamp, rounded for logs."""
    return round((time.perf_counter() - start) * 1000, 2)


def timed(event_name: str):
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                log_event(f"{event_name}.success", elapsed_ms=elapsed_ms(start))
                return result
            except Exception as exc:
                log_event(f"{event_name}.error", elapsed_ms=elapsed_ms(start), error=str(exc))
                raise
        return wrapper
    return decorator
