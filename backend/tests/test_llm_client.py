import os
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_llm_client_imports_without_a_qwen_key() -> None:
    environment = os.environ.copy()
    environment["QWEN_API_KEY"] = ""
    environment["LLM_PROVIDER"] = "qianfan"  # legacy setting must be ignored
    command = (
        "from backend.shared import llm_client; "
        "assert llm_client.llm_enabled() is False"
    )

    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_llm_client_reads_qwen_key_from_environment_at_call_time(monkeypatch) -> None:
    from backend.shared import llm_client

    captured = {}

    class FakeClient:
        pass

    def fake_openai(*, api_key, base_url, http_client):
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        captured["http_client"] = http_client
        return FakeClient()

    monkeypatch.setenv("LLM_PROVIDER", "qianfan")  # legacy setting must be ignored
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setattr(llm_client, "OpenAI", fake_openai)
    monkeypatch.setenv("QWEN_API_KEY", "test-key")

    client = llm_client.get_llm_client()

    assert isinstance(client, FakeClient)
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert captured["http_client"]._trust_env is False
    captured["http_client"].close()


def test_llm_client_supports_any_configured_qwen_model(monkeypatch) -> None:
    from backend.shared import llm_client

    captured = {}

    class FakeClient:
        pass

    def fake_openai(*, api_key, base_url, **kwargs):
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        return FakeClient()

    monkeypatch.setattr(llm_client, "OpenAI", fake_openai)
    monkeypatch.setenv("QWEN_API_KEY", "qwen-test-key")
    monkeypatch.setenv("LLM_MODEL", "qwen-max")

    client = llm_client.get_llm_client()

    assert isinstance(client, FakeClient)
    assert llm_client.get_llm_model() == "qwen-max"
    assert captured == {
        "api_key": "qwen-test-key",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }


def test_llm_client_uses_qwen_default_model_when_no_model_is_configured(monkeypatch) -> None:
    from backend.shared import llm_client

    monkeypatch.delenv("LLM_MODEL", raising=False)

    assert llm_client.get_llm_model() == "qwen-plus"


def test_llm_client_uses_dashscope_default_when_qwen_base_url_is_blank(monkeypatch) -> None:
    from backend.shared import llm_client

    captured = {}

    class FakeClient:
        pass

    def fake_openai(*, api_key, base_url, **kwargs):
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        return FakeClient()

    monkeypatch.setattr(llm_client, "OpenAI", fake_openai)
    monkeypatch.setenv("QWEN_API_KEY", "qwen-test-key")
    monkeypatch.setenv("QWEN_BASE_URL", "")

    llm_client.get_llm_client()

    assert captured["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
