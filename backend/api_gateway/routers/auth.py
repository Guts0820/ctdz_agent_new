"""登录签发与身份回显。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api_gateway import accounts
from backend.api_gateway.auth import tokens
from backend.api_gateway.auth.dependencies import Principal, get_principal

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# 登录失败故意不区分"用户不存在"与"密码错误"，避免用户名枚举
LOGIN_FAILED_DETAIL = "用户名或密码不正确"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


def _public_account(account: accounts.Account) -> dict:
    """对外只暴露身份与归属，不含任何口令材料（Account 本身也没有哈希字段）。"""
    return {
        "account_id": account.account_id,
        "role": account.role,
        "username": account.username,
        "student_id": account.student_id,
        "teacher_id": account.teacher_id,
    }


@router.post("/login")
def login(request: LoginRequest) -> dict:
    account = accounts.verify_credentials(request.username, request.password)
    if account is None:
        raise HTTPException(status_code=401, detail=LOGIN_FAILED_DETAIL)
    return {
        "access_token": tokens.issue_token(account),
        "token_type": "bearer",
        "expires_in": tokens.AUTH_JWT_TTL_HOURS * 3600,
        "account": _public_account(account),
    }


@router.get("/me")
def me(principal: Principal = Depends(get_principal)) -> dict:
    account = accounts.get_by_account_id(principal.account_id)
    if account is None or not account.is_active:
        raise HTTPException(status_code=401, detail="账号不存在或已停用")
    return {"principal": principal.model_dump(), "account": _public_account(account)}
