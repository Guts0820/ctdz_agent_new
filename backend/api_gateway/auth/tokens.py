"""JWT 签发与校验（HS256）。"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from backend.shared.config import AUTH_JWT_SECRET, AUTH_JWT_TTL_HOURS

ALGORITHM = "HS256"

NOT_CONFIGURED_WARNING = (
    "[auth] ⚠ AUTH_JWT_SECRET 未配置：本进程使用随机临时密钥签发的令牌在重启后全部失效。"
    "生产环境必须在 backend/.env 里配置固定密钥。"
)

_runtime_secret: str | None = None


def resolve_secret() -> str:
    """返回签名密钥；未配置时打印显式警告并生成进程内稳定的临时密钥。

    绝不静默回退到硬编码默认值 —— 那会让任何人都能伪造令牌。
    """
    global _runtime_secret
    if AUTH_JWT_SECRET:
        return AUTH_JWT_SECRET
    if _runtime_secret is None:
        _runtime_secret = secrets.token_urlsafe(48)
        print(NOT_CONFIGURED_WARNING, flush=True)
    return _runtime_secret


def issue_token(account: Any, *, ttl_hours: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    hours = AUTH_JWT_TTL_HOURS if ttl_hours is None else ttl_hours
    payload = {
        "sub": account.account_id,
        "role": account.role,
        "student_id": account.student_id,
        "teacher_id": account.teacher_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=hours)).timestamp()),
    }
    return jwt.encode(payload, resolve_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """校验签名与有效期；失败抛 ``jwt.PyJWTError`` 子类。"""
    return jwt.decode(token, resolve_secret(), algorithms=[ALGORITHM])
