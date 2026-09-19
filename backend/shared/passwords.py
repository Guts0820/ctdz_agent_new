"""密码哈希：stdlib ``scrypt``，不引入第三方依赖。

存储格式 ``scrypt$<salt_b64>$<digest_b64>``，每次哈希都用新的 16 字节盐，
所以同一密码两次入库的密文不同（不可反查、不可撞库比对）。
"""

import base64
import hashlib
import hmac
import os

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P, _DKLEN = 2**14, 8, 1, 32
_ALGORITHM = "scrypt"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        str(password).encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
    )
    return f"{_ALGORITHM}${base64.b64encode(salt).decode()}${base64.b64encode(derived).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码；存储内容损坏或算法不认识时返回 False，不抛异常。"""
    try:
        algorithm, salt_b64, digest_b64 = str(stored).split("$")
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(digest_b64, validate=True)
    except (AttributeError, ValueError, TypeError):
        return False
    if algorithm != _ALGORITHM or not salt or not expected:
        return False
    derived = hashlib.scrypt(
        str(password).encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
    )
    return hmac.compare_digest(derived, expected)
