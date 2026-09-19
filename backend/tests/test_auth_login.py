"""JWT 登录签发、身份解析与失败语义。"""

import sqlite3
from pathlib import Path

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api_gateway import accounts
from backend.api_gateway.auth import dependencies, tokens
from backend.api_gateway.routers import auth
from backend.tools import init_sqlite_database

TEST_SECRET = "unit-test-secret"
PASSWORD = "pw123456"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch) -> TestClient:
    database = tmp_path / "auth.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(init_sqlite_database.SCHEMA)
    monkeypatch.setattr(accounts, "DATABASE_PATH", str(database))
    monkeypatch.setattr(tokens, "AUTH_JWT_SECRET", TEST_SECRET)
    monkeypatch.setattr(tokens, "AUTH_JWT_TTL_HOURS", 12)
    app = FastAPI()
    app.include_router(auth.router)
    return TestClient(app)


@pytest.fixture()
def seeded_account(client) -> accounts.Account:
    return accounts.create_account("student", "xiaoming", PASSWORD, student_id="S-0001")


def login(client: TestClient, username: str, password: str):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_login_returns_token_for_valid_credentials(client, seeded_account) -> None:
    response = login(client, "xiaoming", PASSWORD)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 12 * 3600
    assert body["account"] == {
        "account_id": seeded_account.account_id,
        "role": "student",
        "username": "xiaoming",
        "student_id": "S-0001",
        "teacher_id": None,
    }
    assert "password" not in str(body)


def test_login_rejects_wrong_password(client, seeded_account) -> None:
    response = login(client, "xiaoming", "wrong-password")

    assert response.status_code == 401
    assert response.json()["detail"] == auth.LOGIN_FAILED_DETAIL


def test_login_does_not_leak_whether_the_user_exists(client, seeded_account) -> None:
    """用户名枚举防护：未知用户与密码错误必须返回同一条信息。"""
    unknown = login(client, "nobody", PASSWORD)
    wrong = login(client, "xiaoming", "wrong-password")

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_inactive_account_cannot_login(client) -> None:
    account = accounts.create_account("teacher", "t001", PASSWORD, teacher_id="T001")
    accounts.set_active(account.account_id, False)

    assert login(client, "t001", PASSWORD).status_code == 401


def test_token_decodes_to_expected_role_and_subject(client, seeded_account) -> None:
    token = login(client, "xiaoming", PASSWORD).json()["access_token"]

    payload = jwt.decode(token, TEST_SECRET, algorithms=["HS256"])

    assert payload["sub"] == seeded_account.account_id
    assert payload["role"] == "student"
    assert payload["student_id"] == "S-0001"
    assert payload["teacher_id"] is None
    assert payload["exp"] > payload["iat"]


def test_expired_token_is_rejected(client, seeded_account, monkeypatch) -> None:
    monkeypatch.setattr(tokens, "AUTH_JWT_TTL_HOURS", -1)  # 签发即过期
    token = login(client, "xiaoming", PASSWORD).json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == dependencies.INVALID_TOKEN_DETAIL


def test_token_signed_with_another_secret_is_rejected(client, seeded_account) -> None:
    forged = jwt.encode(
        {"sub": seeded_account.account_id, "role": "admin", "exp": 9999999999},
        "attacker-secret",
        algorithm="HS256",
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_me_returns_the_principal_for_a_valid_token(client, seeded_account) -> None:
    token = login(client, "xiaoming", PASSWORD).json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["principal"] == {
        "account_id": seeded_account.account_id,
        "role": "student",
        "student_id": "S-0001",
        "teacher_id": None,
    }


def test_me_rejects_missing_or_malformed_authorization(client) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Token abc"}).status_code == 401
    # 注意：HTTP 头只能放 ASCII，这里用畸形但合法的头值
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer aaa.bbb.ccc"}).status_code == 401


def test_me_rejects_a_token_without_the_required_claims(client, seeded_account) -> None:
    token = jwt.encode({"role": "student", "exp": 9999999999}, TEST_SECRET, algorithm="HS256")

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_me_rejects_a_deleted_account(client) -> None:
    account = accounts.create_account("student", "temp", PASSWORD, student_id="S-0002")
    token = tokens.issue_token(account)
    with sqlite3.connect(accounts.DATABASE_PATH) as connection:
        connection.execute("DELETE FROM account WHERE account_id = ?", (account.account_id,))
        connection.commit()

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_missing_secret_falls_back_to_a_runtime_secret_with_a_warning(monkeypatch, capsys) -> None:
    """没配置密钥时不能静默用固定默认值，否则任何人可伪造令牌。"""
    monkeypatch.setattr(tokens, "AUTH_JWT_SECRET", "")
    monkeypatch.setattr(tokens, "_runtime_secret", None)

    account = accounts.Account(account_id="ACC-1", role="admin", username="root")
    first = tokens.issue_token(account)
    second = tokens.issue_token(account)

    assert tokens.resolve_secret()  # 进程内稳定
    assert jwt.decode(first, tokens.resolve_secret(), algorithms=["HS256"])["sub"] == "ACC-1"
    assert tokens.decode_token(second)["role"] == "admin"
    assert "AUTH_JWT_SECRET 未配置" in capsys.readouterr().out


def test_gateway_registers_the_auth_router() -> None:
    source = (Path(__file__).resolve().parents[1] / "api_gateway" / "app.py").read_text(encoding="utf-8")

    assert "auth.router," in source
    assert "    auth," in source
