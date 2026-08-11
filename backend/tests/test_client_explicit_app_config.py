from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

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


def test_client_passes_explicit_app_config_to_tool_runtime_context() -> None:
    app_config = _app_config()
    client = DeerFlowClient(app_config=app_config)
    agent = MagicMock()
    agent.stream.return_value = iter([{"messages": [AIMessage(content="ok", id="ai-1")]}])

    with (
        patch.object(client, "_ensure_agent"),
        patch.object(client, "_agent", agent),
        patch("deerflow.runtime.checkpointer.get_checkpointer", return_value=None),
    ):
        list(client.stream("inspect evidence", thread_id="explicit-config"))

    runtime_context = agent.stream.call_args.kwargs["context"]
    assert runtime_context["app_config"] is app_config
