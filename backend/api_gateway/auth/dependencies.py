"""身份解析与角色守卫。

认证统一走 ``Depends(get_principal)``；**归属判断用显式守卫**（URL 里的资源标识与身份
的映射关系因路由而异：``student_id`` 在路径、``class_id`` 在 body、``teacher_id`` 在查询串，
中间件在不了解语义的情况下无法判断归属）。守卫写一次，所有路由复用。
"""

from typing import Literal, Optional

import jwt
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from backend.api_gateway.auth import class_scope
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


def authorize_student(principal: Principal, student_id: str) -> None:
    """学生只能访问自己；教师需该生属于本班；管理员放行。"""
    if principal.role == "admin":
        return
    if principal.role == "student":
        if principal.student_id != student_id:
            raise HTTPException(status_code=403, detail="无权访问其他学生的数据")
        return
    if not class_scope.teacher_owns_student(principal.teacher_id, student_id):
        raise HTTPException(status_code=403, detail="无权访问非本班学生的数据")


def authorize_teacher_class(principal: Principal, class_id: str | None) -> None:
    """教师只能访问自己任教的班级；学生无权访问班级维度数据。"""
    if principal.role == "admin":
        return
    if principal.role != "teacher":
        raise HTTPException(status_code=403, detail="需要教师权限")
    if not class_scope.teacher_owns_class(principal.teacher_id, class_id):
        raise HTTPException(status_code=403, detail="无权访问非本班数据")


def require_admin(principal: Principal) -> None:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
