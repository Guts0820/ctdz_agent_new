"""网关到内部服务的可信边界：共享令牌的签发与校验。

网关侧用 :func:`internal_headers` 注入 ``X-Internal-Token``，服务侧用
:func:`require_internal_token` 校验。未配置 ``INTERNAL_API_TOKEN`` 时两边都退化为
不校验 —— 本地开发不需要额外配置，但生产必须配置，否则这道边界形同虚设。
"""

from fastapi import Header, HTTPException, Request

from backend.shared.config import INTERNAL_API_TOKEN

TOKEN_HEADER = "X-Internal-Token"

# 健康检查必须放行：网关的 /health 会聚合探测所有下游，拦截它会让整个网关自报不健康。
OPEN_PATHS = frozenset({"/health"})


def internal_headers() -> dict[str, str]:
    """网关调用下游时附带的请求头；未配置令牌时返回空字典。"""
    return {TOKEN_HEADER: INTERNAL_API_TOKEN} if INTERNAL_API_TOKEN else {}


def require_internal_token(
    request: Request,
    x_internal_token: str | None = Header(default=None, alias=TOKEN_HEADER),
) -> None:
    """内部接口只信任网关。"""
    if not INTERNAL_API_TOKEN or request.url.path in OPEN_PATHS:
        return
    if x_internal_token != INTERNAL_API_TOKEN:
        raise HTTPException(status_code=401, detail="内部调用凭据无效")
