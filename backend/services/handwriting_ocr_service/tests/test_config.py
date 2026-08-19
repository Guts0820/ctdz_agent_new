import os

from app.config import Settings
import pytest


def test_paddleocr_vl_uses_cpu_by_default_for_local_development(monkeypatch) -> None:
    monkeypatch.delenv("PADDLEOCR_VL_DEVICE", raising=False)
    monkeypatch.delenv("OCR_RUNTIME_ENV", raising=False)
    monkeypatch.delenv("PADDLEOCR_VL_PIPELINE_VERSION", raising=False)

    settings = Settings.from_env()

    assert settings.paddleocr_vl_device == "cpu"
    assert settings.paddleocr_vl_pipeline_version == "v1.6"


def test_paddleocr_vl_uses_gpu_in_production_unless_explicitly_overridden(monkeypatch) -> None:
    monkeypatch.setenv("OCR_RUNTIME_ENV", "production")
    monkeypatch.delenv("PADDLEOCR_VL_DEVICE", raising=False)

    assert Settings.from_env().paddleocr_vl_device == "gpu"

    monkeypatch.setenv("PADDLEOCR_VL_DEVICE", "cpu")

    assert Settings.from_env().paddleocr_vl_device == "cpu"


def test_qwen_is_the_default_ocr_engine_and_uses_the_configured_default_model(monkeypatch) -> None:
    monkeypatch.delenv("OCR_ENGINE", raising=False)
    monkeypatch.delenv("QWEN_MODEL", raising=False)
    monkeypatch.setenv("QWEN_API_KEY", "test-key")

    settings = Settings.from_env()

    assert settings.ocr_engine == "qwen"
    assert settings.qwen_model == "qwen-3.7plus"
    assert settings.qwen_is_configured is True


def test_ocr_configuration_disables_environment_proxy_usage(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")

    Settings.from_env()

    assert os.environ["NO_PROXY"] == "*"
    assert os.environ["no_proxy"] == "*"


def test_rejects_an_unsupported_paddleocr_vl_pipeline_version(monkeypatch) -> None:
    monkeypatch.setenv("PADDLEOCR_VL_PIPELINE_VERSION", "v2")

    with pytest.raises(ValueError, match="PADDLEOCR_VL_PIPELINE_VERSION"):
        Settings.from_env()
