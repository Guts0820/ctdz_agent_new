"""内部服务默认只监听回环地址（堵住绕过网关直连的通道）。"""

import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND.parent


def _print_bind_host(env_overrides: dict[str, str]) -> str:
    """在子进程里读配置，避免 reload 污染同会话内其它测试。"""
    environment = os.environ.copy()
    environment.pop("SERVICE_BIND_HOST", None)
    environment.update(env_overrides)
    result = subprocess.run(
        [sys.executable, "-c", "from backend.shared.config import SERVICE_BIND_HOST; print(SERVICE_BIND_HOST)"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_every_uvicorn_entrypoint_binds_the_configured_host() -> None:
    """任何拉起 uvicorn 的入口都不得硬编码全网卡监听，且必须用 SERVICE_BIND_HOST。

    只扫生产代码：本测试自身要写出 ``host="0.0.0.0"`` 这个字面量来断言它不存在。
    """
    offenders = []
    for path in sorted(BACKEND.rglob("*.py")):
        if BACKEND / "tests" in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        if "uvicorn.run(" not in source:
            continue
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        if 'host="0.0.0.0"' in source:
            offenders.append(f"{relative}（硬编码 0.0.0.0）")
        elif "SERVICE_BIND_HOST" not in source:
            offenders.append(f"{relative}（未引用 SERVICE_BIND_HOST）")
        elif "host=SERVICE_BIND_HOST" not in source:
            offenders.append(f"{relative}（SERVICE_BIND_HOST 未传给 uvicorn）")
    assert offenders == [], offenders


def test_bind_host_config_defaults_to_loopback() -> None:
    assert _print_bind_host({}) == "127.0.0.1"


def test_bind_host_config_follows_the_environment() -> None:
    """需要外部访问时由环境变量显式放开，而不是改代码。"""
    assert _print_bind_host({"SERVICE_BIND_HOST": "0.0.0.0"}) == "0.0.0.0"
