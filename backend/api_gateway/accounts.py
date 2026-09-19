"""账号仓储：密码哈希的唯一入口，哈希不出这个模块。

上层（登录接口、角色守卫）只通过 :func:`verify_credentials` 校验凭据，
拿到的 :class:`Account` **不含** ``password_hash`` —— 这样接口层不可能误把哈希
序列化出去。
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from backend.shared.config import DATABASE_PATH as CONFIGURED_DATABASE_PATH
from backend.shared.id_utils import generate_id
from backend.shared.passwords import hash_password, verify_password

# 允许测试 monkeypatch 到临时库
DATABASE_PATH = CONFIGURED_DATABASE_PATH

VALID_ROLES = ("student", "teacher", "admin")


class DuplicateUsernameError(RuntimeError):
    """用户名已存在。"""


@dataclass(frozen=True)
class Account:
    """对外可见的账号信息；刻意不含 password_hash。"""

    account_id: str
    role: str
    username: str
    student_id: Optional[str] = None
    teacher_id: Optional[str] = None
    is_active: bool = True
    created_at: str = ""
    password_changed_at: Optional[str] = None


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_account(row: sqlite3.Row) -> Account:
    return Account(
        account_id=str(row["account_id"]),
        role=str(row["role"]),
        username=str(row["username"]),
        student_id=row["student_id"],
        teacher_id=row["teacher_id"],
        is_active=bool(row["is_active"]),
        created_at=str(row["created_at"]),
        password_changed_at=row["password_changed_at"],
    )


def validate_account_input(role: str, username: str, student_id: str | None, teacher_id: str | None) -> str:
    role = str(role or "").strip().lower()
    if role not in VALID_ROLES:
        raise ValueError(f"角色必须是 {VALID_ROLES} 之一")
    if not str(username or "").strip():
        raise ValueError("用户名不能为空")
    if role == "student" and not student_id:
        raise ValueError("学生账号必须绑定 student_id")
    if role == "teacher" and not teacher_id:
        raise ValueError("教师账号必须绑定 teacher_id")
    return role


def create_account(
    role: str,
    username: str,
    password: str,
    *,
    student_id: str | None = None,
    teacher_id: str | None = None,
    account_id: str | None = None,
) -> Account:
    role = validate_account_input(role, username, student_id, teacher_id)
    if not password:
        raise ValueError("密码不能为空")
    record_id = account_id or generate_id("ACC")
    now = _now()
    try:
        with _connect() as connection:
            connection.execute(
                """INSERT INTO account
                   (account_id, role, username, password_hash, student_id, teacher_id,
                    is_active, created_at, password_changed_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (record_id, role, str(username).strip(), hash_password(password), student_id, teacher_id, now, now),
            )
            connection.commit()
    except sqlite3.IntegrityError as error:
        raise DuplicateUsernameError(f"用户名已存在：{username}") from error
    return Account(
        account_id=record_id,
        role=role,
        username=str(username).strip(),
        student_id=student_id,
        teacher_id=teacher_id,
        is_active=True,
        created_at=now,
        password_changed_at=now,
    )


def get_by_username(username: str) -> Account | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM account WHERE username = ?", (str(username or "").strip(),)
        ).fetchone()
    return _to_account(row) if row else None


def get_by_student_id(student_id: str) -> Account | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM account WHERE student_id = ? ORDER BY created_at LIMIT 1", (student_id,)
        ).fetchone()
    return _to_account(row) if row else None


def get_by_account_id(account_id: str) -> Account | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM account WHERE account_id = ?", (account_id,)).fetchone()
    return _to_account(row) if row else None


def set_password(account_id: str, new_password: str) -> bool:
    if not new_password:
        raise ValueError("密码不能为空")
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE account SET password_hash = ?, password_changed_at = ? WHERE account_id = ?",
            (hash_password(new_password), _now(), account_id),
        )
        connection.commit()
    return cursor.rowcount > 0


def set_active(account_id: str, is_active: bool) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE account SET is_active = ? WHERE account_id = ?",
            (1 if is_active else 0, account_id),
        )
        connection.commit()
    return cursor.rowcount > 0


def verify_credentials(username: str, password: str) -> Account | None:
    """校验用户名/密码；失败（含账号停用）统一返回 None，不区分原因。"""
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM account WHERE username = ?", (str(username or "").strip(),)
        ).fetchone()
    if row is None or not bool(row["is_active"]):
        return None
    if not verify_password(password or "", str(row["password_hash"])):
        return None
    return _to_account(row)
