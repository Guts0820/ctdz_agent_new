"""身份解析：从 Bearer 令牌得到 :class:`Principal`。

角色守卫（``authorize_student`` / ``require_admin`` 等）在 Task 1.6 补，本模块先把
"认证"这一层统一掉，路由只声明 ``Depends(get_principal)``。
"""

from typing import Literal, Optional

import jwt
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from backend.api_gateway.auth.tokens import decode_token

MISSING_TOKEN_DETAIL = "缺少访问令牌"
INVALID_TOKEN_DETAIL = "访问令牌无效或已过期"


class Principal(BaseModel):
    """令牌解出的调用者身份。"""

    account_id: str
    role: Literal["student", "teacher", "admin"]
    student_id: Optional[str] = None
    teacher_id: Optional[str] = None


def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    """解析 ``Authorization: Bearer <token>``；缺令牌/无效令牌统一 401。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail=MISSING_TOKEN_DETAIL)
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail=INVALID_TOKEN_DETAIL) from error
    try:
        return Principal(
            account_id=str(payload["sub"]),
            role=payload["role"],
            student_id=payload.get("student_id"),
            teacher_id=payload.get("teacher_id"),
        )
    except (KeyError, ValueError, TypeError) as error:
        raise HTTPException(status_code=401, detail=INVALID_TOKEN_DETAIL) from error
