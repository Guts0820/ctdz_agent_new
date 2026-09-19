"""密码哈希：加盐、不可逆、损坏数据不抛异常。"""

from backend.shared.passwords import hash_password, verify_password


def test_hash_is_salted_and_not_reversible() -> None:
    first = hash_password("pw123456")
    second = hash_password("pw123456")

    assert first != second  # 每次加盐
    assert "pw123456" not in first  # 不出现明文
    assert first.startswith("scrypt$")
    assert len(first.split("$")) == 3


def test_verify_accepts_correct_and_rejects_wrong() -> None:
    stored = hash_password("pw123456")

    assert verify_password("pw123456", stored) is True
    assert verify_password("pw123457", stored) is False
    assert verify_password("", stored) is False


def test_verify_returns_false_for_broken_stored_values() -> None:
    for broken in ("垃圾数据", "", "scrypt$only-two-parts", "bcrypt$c2FsdA==$ZGlubmVy", None, 12345):
        assert verify_password("pw123456", broken) is False


def test_verify_rejects_other_algorithm_even_with_valid_base64() -> None:
    import base64

    forged = "md5$" + base64.b64encode(b"saltsalt").decode() + "$" + base64.b64encode(b"digest").decode()

    assert verify_password("pw123456", forged) is False
