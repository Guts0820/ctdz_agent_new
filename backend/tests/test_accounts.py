"""账号仓储：哈希不出模块、角色约束、凭据校验。"""

import dataclasses
import sqlite3
from pathlib import Path

import pytest

from backend.api_gateway import accounts
from backend.tools import init_sqlite_database


@pytest.fixture()
def account_db(tmp_path: Path, monkeypatch) -> Path:
    database = tmp_path / "accounts.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(init_sqlite_database.SCHEMA)
    monkeypatch.setattr(accounts, "DATABASE_PATH", str(database))
    return database


def test_account_exposes_no_password_hash() -> None:
    """仓储返回的 Account 里不能有哈希字段，接口层就没机会把它序列化出去。"""
    fields = {field.name for field in dataclasses.fields(accounts.Account)}

    assert "password_hash" not in fields
    assert fields == {
        "account_id",
        "role",
        "username",
        "student_id",
        "teacher_id",
        "is_active",
        "created_at",
        "password_changed_at",
    }


def test_create_and_read_back_an_account(account_db) -> None:
    created = accounts.create_account("student", "xiaoming", "pw123456", student_id="S-0001")

    assert created.account_id.startswith("ACC-")
    assert created.role == "student"
    assert accounts.get_by_username("xiaoming") == created
    assert accounts.get_by_student_id("S-0001") == created

    # 库里存的是哈希，不是明文
    with sqlite3.connect(account_db) as connection:
        stored = connection.execute(
            "SELECT password_hash FROM account WHERE account_id = ?", (created.account_id,)
        ).fetchone()[0]
    assert stored.startswith("scrypt$")
    assert "pw123456" not in stored


def test_duplicate_username_is_rejected(account_db) -> None:
    accounts.create_account("student", "xiaoming", "pw123456", student_id="S-0001")

    with pytest.raises(accounts.DuplicateUsernameError):
        accounts.create_account("student", "xiaoming", "pw654321", student_id="S-0002")


def test_role_and_binding_validation(account_db) -> None:
    with pytest.raises(ValueError):
        accounts.create_account("parent", "someone", "pw123456")
    with pytest.raises(ValueError):
        accounts.create_account("student", "xiaoming", "pw123456")  # 缺 student_id
    with pytest.raises(ValueError):
        accounts.create_account("teacher", "t001", "pw123456")  # 缺 teacher_id
    with pytest.raises(ValueError):
        accounts.create_account("admin", "  ", "pw123456")  # 空用户名
    with pytest.raises(ValueError):
        accounts.create_account("admin", "root", "")  # 空密码

    assert accounts.create_account("admin", "root", "pw123456").role == "admin"


def test_verify_credentials_happy_path_and_failures(account_db) -> None:
    accounts.create_account("teacher", "t001", "pw123456", teacher_id="T001")

    assert accounts.verify_credentials("t001", "pw123456") is not None
    assert accounts.verify_credentials("t001", "wrong") is None
    assert accounts.verify_credentials("unknown", "pw123456") is None
    assert accounts.verify_credentials("t001", "") is None


def test_inactive_account_cannot_verify(account_db) -> None:
    account = accounts.create_account("student", "xiaoming", "pw123456", student_id="S-0001")

    assert accounts.set_active(account.account_id, False) is True

    assert accounts.verify_credentials("xiaoming", "pw123456") is None
    assert accounts.set_active(account.account_id, True) is True
    assert accounts.verify_credentials("xiaoming", "pw123456") is not None


def test_set_password_rotates_the_hash(account_db) -> None:
    account = accounts.create_account("student", "xiaoming", "pw123456", student_id="S-0001")
    with sqlite3.connect(account_db) as connection:
        before = connection.execute(
            "SELECT password_hash FROM account WHERE account_id = ?", (account.account_id,)
        ).fetchone()[0]

    assert accounts.set_password(account.account_id, "pw654321") is True

    with sqlite3.connect(account_db) as connection:
        after, changed_at = connection.execute(
            "SELECT password_hash, password_changed_at FROM account WHERE account_id = ?",
            (account.account_id,),
        ).fetchone()
    assert after != before
    assert changed_at
    assert accounts.verify_credentials("xiaoming", "pw654321") is not None
    assert accounts.verify_credentials("xiaoming", "pw123456") is None
    assert accounts.set_password("ACC-NOPE", "pw654321") is False


def test_migration_adds_the_account_table_to_a_legacy_database(tmp_path: Path) -> None:
    """老库没有 account 表；重建 schema 后必须能建账号（init 脚本负责）。"""
    legacy = tmp_path / "legacy.db"
    with sqlite3.connect(legacy) as connection:
        connection.executescript(
            "CREATE TABLE students (student_id TEXT PRIMARY KEY, student_class TEXT);"
        )

    with sqlite3.connect(legacy) as connection:
        connection.executescript(init_sqlite_database.SCHEMA)
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}

    assert "account" in tables
    assert {"idx_account_student", "idx_account_teacher"} <= indexes


def test_repository_never_exposes_the_hash() -> None:
    """结构测试：把库行映射成 Account 的函数里不许碰 password_hash。"""
    source = Path(accounts.__file__).read_text(encoding="utf-8")
    mapper = source.split("def _to_account")[1].split("\ndef ")[0]

    assert "password_hash" not in mapper
    assert "password_hash=row" not in source
