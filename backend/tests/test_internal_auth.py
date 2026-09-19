"""网关 → 内部服务的调用令牌边界。"""

import re
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GATEWAY_SERVICES = REPOSITORY_ROOT / "backend" / "api_gateway" / "services"


def build_app(monkeypatch, token: str) -> TestClient:
    """按给定令牌配置搭一个受保护的应用；monkeypatch 会在用例结束后自动还原。"""
    from backend.shared import internal_auth

    monkeypatch.setattr(internal_auth, "INTERNAL_API_TOKEN", token)
    app = FastAPI(dependencies=[Depends(internal_auth.require_internal_token)])

    @app.get("/internal/api/v1/ping")
    def ping():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    return TestClient(app)


def test_internal_endpoint_rejects_missing_token(monkeypatch) -> None:
    client = build_app(monkeypatch, "s3cret")

    assert client.get("/internal/api/v1/ping").status_code == 401


def test_internal_endpoint_rejects_wrong_token(monkeypatch) -> None:
    client = build_app(monkeypatch, "s3cret")

    response = client.get("/internal/api/v1/ping", headers={"X-Internal-Token": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "内部调用凭据无效"


def test_internal_endpoint_accepts_valid_token(monkeypatch) -> None:
    client = build_app(monkeypatch, "s3cret")

    response = client.get("/internal/api/v1/ping", headers={"X-Internal-Token": "s3cret"})

    assert response.status_code == 200


def test_internal_endpoint_open_when_token_unset(monkeypatch) -> None:
    """未配置 token 时保持开发可用，避免破坏本地联调。"""
    client = build_app(monkeypatch, "")

    assert client.get("/internal/api/v1/ping").status_code == 200


def test_health_check_stays_open(monkeypatch) -> None:
    """网关的 /health 会聚合探测所有下游，被拦掉会让网关自报不健康。"""
    client = build_app(monkeypatch, "s3cret")

    assert client.get("/health").status_code == 200


def test_internal_headers_only_present_when_configured(monkeypatch) -> None:
    from backend.shared import internal_auth

    monkeypatch.setattr(internal_auth, "INTERNAL_API_TOKEN", "s3cret")
    assert internal_auth.internal_headers() == {internal_auth.TOKEN_HEADER: "s3cret"}

    monkeypatch.setattr(internal_auth, "INTERNAL_API_TOKEN", "")
    assert internal_auth.internal_headers() == {}


def test_gateway_client_sends_the_token(monkeypatch) -> None:
    """网关调用下游时必须带上令牌，否则服务侧开校验后整条链路 401。"""
    from backend.api_gateway.services import analysis_client
    from backend.shared import internal_auth

    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"judge_result": "correct"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(internal_auth, "INTERNAL_API_TOKEN", "s3cret")
    monkeypatch.setattr(analysis_client.requests, "post", fake_post)

    analysis_client.analyze_submission({"student_id": "S-0001"})

    assert captured["headers"] == {"X-Internal-Token": "s3cret"}


def test_every_gateway_service_call_passes_internal_headers() -> None:
    """结构测试：新增的下游调用不能漏掉令牌请求头（GET 也算，KG 客户端就是 GET）。"""
    offenders = []
    for path in sorted(GATEWAY_SERVICES.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        calls = len(re.findall(r"requests\.(get|post|put|delete|patch)\(", source))
        if not calls:
            continue
        if "internal_headers" not in source:
            offenders.append(f"{path.name}（未注入 X-Internal-Token）")
        elif source.count("headers=internal_headers()") != calls:
            offenders.append(f"{path.name}（{calls} 处调用只有 {source.count('headers=internal_headers()')} 处注入）")
    assert offenders == [], offenders


def test_every_downstream_service_requires_the_token() -> None:
    """结构测试：网关会调用的下游服务必须挂上令牌校验。"""
    service_mains = [
        REPOSITORY_ROOT / "backend" / "services" / name / "main.py"
        for name in (
            "analysis_service",
            "error_analysis_service",
            "knowledge_service",
            "teaching_service",
            "teacher_service",
            "state_service",
            "review_service",
            "knowledge_graph_service",
        )
    ]
    service_mains.append(
        REPOSITORY_ROOT / "backend" / "services" / "handwriting_ocr_service" / "app" / "main.py"
    )

    offenders = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in service_mains
        if "dependencies=[Depends(require_internal_token)]" not in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], offenders


def test_gateway_itself_stays_public() -> None:
    """网关是对外入口，不能挂内部令牌校验，否则前端全 401。"""
    source = (REPOSITORY_ROOT / "backend" / "api_gateway" / "app.py").read_text(encoding="utf-8")

    assert "require_internal_token" not in source
