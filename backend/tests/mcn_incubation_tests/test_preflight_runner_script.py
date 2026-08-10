from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "run_incubation_preflight.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_incubation_preflight", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_final_response_keeps_last_ai_message_and_usage() -> None:
    module = _load_script()

    class FakeClient:
        def stream(self, _prompt, **_kwargs):
            yield SimpleNamespace(type="messages-tuple", data={"type": "ai", "id": "draft", "content": "draft"})
            yield SimpleNamespace(type="messages-tuple", data={"type": "ai", "id": "final", "content": "孵化"})
            yield SimpleNamespace(type="messages-tuple", data={"type": "ai", "id": "final", "content": "方案"})
            yield SimpleNamespace(
                type="end",
                data={"usage": {"input_tokens": 120, "output_tokens": 80, "total_tokens": 200}},
            )

    output, usage = module.collect_final_response(
        FakeClient(),
        prompt="test",
        thread_id="thread-1",
    )

    assert output == "孵化方案"
    assert usage == {"input_tokens": 120, "output_tokens": 80, "total_tokens": 200}


def test_select_cases_rejects_unknown_ids_and_preserves_requested_order() -> None:
    module = _load_script()
    cases = [SimpleNamespace(case_id="M01"), SimpleNamespace(case_id="B01")]

    selected = module.select_cases(cases, ("B01", "M01"))

    assert [case.case_id for case in selected] == ["B01", "M01"]
    try:
        module.select_cases(cases, ("missing",))
    except ValueError as exc:
        assert "unknown case ids" in str(exc)
    else:
        raise AssertionError("unknown case ids must fail")


def test_collect_final_response_rejects_deerflow_error_fallbacks() -> None:
    module = _load_script()

    class FailingClient:
        def stream(self, _prompt, **_kwargs):
            yield SimpleNamespace(
                type="messages-tuple",
                data={
                    "type": "ai",
                    "id": "error",
                    "content": "Provider unavailable",
                    "additional_kwargs": {
                        "deerflow_error_fallback": True,
                        "error_reason": "transient",
                        "error_type": "APIConnectionError",
                    },
                },
            )
            yield SimpleNamespace(type="end", data={"usage": {}})

    with pytest.raises(module.ModelFallbackError) as error:
        module.collect_final_response(
            FailingClient(),
            prompt="test",
            thread_id="thread-1",
        )

    assert error.value.error_code == "llm_transient"
