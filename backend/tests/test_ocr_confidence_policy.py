import importlib


def test_ocr_confidence_threshold_defaults_to_095_and_allows_environment_override(
    monkeypatch,
) -> None:
    config = importlib.import_module("backend.shared.config")
    with monkeypatch.context() as isolated:
        isolated.delenv("OCR_MIN_CONFIDENCE", raising=False)
        config = importlib.reload(config)

        assert config.OCR_MIN_CONFIDENCE == 0.95

        isolated.setenv("OCR_MIN_CONFIDENCE", "0.97")
        config = importlib.reload(config)

        assert config.OCR_MIN_CONFIDENCE == 0.97

    importlib.reload(config)
