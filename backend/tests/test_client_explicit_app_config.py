from __future__ import annotations

import pytest

from deerflow.client import DeerFlowClient
from deerflow.config.app_config import AppConfig


def _app_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "sandbox": {
                "use": "deerflow.sandbox.local:LocalSandboxProvider",
            }
        }
    )


def test_client_accepts_explicit_app_config_without_reading_ambient_config(monkeypatch) -> None:
    app_config = _app_config()

    def fail_get_app_config():
        raise AssertionError("ambient app config must not be read")

    monkeypatch.setattr("deerflow.client.get_app_config", fail_get_app_config)

    client = DeerFlowClient(app_config=app_config)

    assert client._app_config is app_config


def test_client_rejects_config_path_with_explicit_app_config() -> None:
    with pytest.raises(ValueError, match="config_path and app_config"):
        DeerFlowClient(config_path="config.yaml", app_config=_app_config())
