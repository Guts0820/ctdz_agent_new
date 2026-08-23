from fastapi import APIRouter, Request

from backend.api_gateway.services.review_proxy_service import proxy_review_request


router = APIRouter(tags=["review-proxy"])


async def _proxy(prefix: str, path: str, request: Request):
    body = await request.body() if request.method in {"POST", "PATCH", "PUT"} else None
    return proxy_review_request(request.method, prefix, path, body)


@router.api_route("/api/review-plans", methods=["GET", "POST"], include_in_schema=False)
async def review_plans_root(request: Request):
    return await _proxy("review-plans", "", request)


@router.api_route("/api/review-plans/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"], include_in_schema=False)
async def review_plans(path: str, request: Request):
    return await _proxy("review-plans", path, request)


@router.api_route("/api/review-sessions/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"], include_in_schema=False)
async def review_sessions(path: str, request: Request):
    return await _proxy("review-sessions", path, request)


@router.api_route("/api/attempts/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"], include_in_schema=False)
async def attempts(path: str, request: Request):
    return await _proxy("attempts", path, request)


@router.api_route("/api/priority-runs", methods=["GET", "POST"], include_in_schema=False)
async def priority_runs_root(request: Request):
    return await _proxy("priority-runs", "", request)


@router.api_route("/api/priority-runs/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def priority_runs(path: str, request: Request):
    return await _proxy("priority-runs", path, request)


@router.api_route("/api/datahub/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def datahub(path: str, request: Request):
    return await _proxy("api/datahub", path, request)
