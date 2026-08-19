import os

import requests


def test_proxy_bypass_disables_environment_proxies_for_requests_and_httpx(monkeypatch) -> None:
    from backend.shared.http_client import configure_proxy_bypass, create_direct_httpx_client

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    configure_proxy_bypass()

    assert requests.utils.get_environ_proxies("https://dashscope.aliyuncs.com") == {}
    with create_direct_httpx_client() as client:
        assert client._trust_env is False


def test_backend_package_configures_proxy_bypass_on_import(monkeypatch) -> None:
    import backend

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    backend.configure_proxy_bypass()

    assert os.environ["NO_PROXY"] == "*"
    assert os.environ["no_proxy"] == "*"


def test_analysis_llm_client_ignores_proxy_environment(monkeypatch) -> None:
    from backend.services.analysis_service import llm_judge

    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setenv("ANALYSIS_LLM_API_KEY", "test-key")
    monkeypatch.setattr(llm_judge, "OpenAI", FakeOpenAI)

    llm_judge._client()

    assert captured["http_client"]._trust_env is False
    captured["http_client"].close()
