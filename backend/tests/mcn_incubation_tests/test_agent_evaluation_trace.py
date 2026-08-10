from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest
from mcn_incubation.agent_evaluation import (
    AgentEventCollector,
    AgentTraceLedger,
    AgentTraceTamperDetected,
    AgentTrialTrace,
)

NOW = datetime(2026, 8, 11, 15, 0, tzinfo=UTC)


def test_agent_event_collector_seals_tool_trajectory_without_credentials() -> None:
    collector = AgentEventCollector()
    collector.consume(
        SimpleNamespace(
            type="messages-tuple",
            data={
                "type": "ai",
                "id": "tool-request",
                "content": "",
                "tool_calls": [
                    {
                        "name": "incubation_project_context",
                        "id": "call-1",
                        "args": {
                            "project_id": "project-a",
                            "api_key": "should-never-be-recorded",
                        },
                    }
                ],
            },
        )
    )
    raw_result = json.dumps(
        {
            "authority": "project_truth_ledger",
            "owner_id": "owner-a",
            "truths": [],
        },
        ensure_ascii=False,
    )
    collector.consume(
        SimpleNamespace(
            type="messages-tuple",
            data={
                "type": "tool",
                "name": "incubation_project_context",
                "tool_call_id": "call-1",
                "content": raw_result,
            },
        )
    )
    collector.consume(
        SimpleNamespace(
            type="messages-tuple",
            data={"type": "ai", "id": "final", "content": "孵化"},
        )
    )
    collector.consume(
        SimpleNamespace(
            type="messages-tuple",
            data={"type": "ai", "id": "final", "content": "判断"},
        )
    )
    collector.consume(
        SimpleNamespace(
            type="end",
            data={
                "usage": {
                    "input_tokens": 120,
                    "output_tokens": 80,
                    "total_tokens": 200,
                }
            },
        )
    )

    observation = collector.finish()

    assert observation.output == "孵化判断"
    assert observation.final_message_id == "final"
    assert observation.usage == {
        "input_tokens": 120,
        "output_tokens": 80,
        "total_tokens": 200,
    }
    assert observation.fallback_error_code is None
    assert len(observation.events) == 2
    tool_call, tool_result = observation.events
    assert tool_call.event_type == "tool_call"
    assert tool_call.arguments == {
        "project_id": "project-a",
        "api_key": "[REDACTED]",
    }
    assert tool_result.event_type == "tool_result"
    assert tool_result.result_sha256 == sha256(raw_result.encode()).hexdigest()
    assert tool_result.safe_result == {
        "authority": "project_truth_ledger",
        "owner_id": "[REDACTED]",
        "truths": [],
    }
    assert "owner-a" not in repr(observation)
    assert "should-never-be-recorded" not in repr(observation)


def test_agent_event_collector_marks_provider_fallback_and_hides_unknown_results() -> None:
    collector = AgentEventCollector()
    collector.consume(
        SimpleNamespace(
            type="messages-tuple",
            data={
                "type": "tool",
                "name": "browser_navigate",
                "tool_call_id": "call-browser",
                "content": "raw browser page",
            },
        )
    )
    collector.consume(
        SimpleNamespace(
            type="messages-tuple",
            data={
                "type": "ai",
                "id": "fallback",
                "content": "Provider unavailable",
                "additional_kwargs": {
                    "deerflow_error_fallback": True,
                    "error_reason": "transient failure",
                },
            },
        )
    )

    observation = collector.finish()

    assert observation.fallback_error_code == "llm_transient_failure"
    assert observation.events[0].safe_result is None
    assert "raw browser page" not in repr(observation)


def test_agent_trace_ledger_binds_tool_surface_and_detects_tampering(tmp_path) -> None:
    ledger = AgentTraceLedger(tmp_path)
    tool_surface = [
        {
            "type": "function",
            "function": {
                "name": "incubation_project_context",
                "description": "Read project truths",
                "parameters": {"type": "object"},
            },
        }
    ]
    ledger.create_run(
        run_id="agent-run-001",
        trial_ids=("M01:initial",),
        actor_sha256="a" * 64,
        tool_surface=tool_surface,
        created_at=NOW,
    )
    trace = AgentTrialTrace(
        trial_id="M01:initial",
        thread_id="thread-M01",
        project_id="project-M01",
        actor_sha256="a" * 64,
        events=(),
        final_message_id="final",
        usage={"total_tokens": 200},
        terminal_error_code=None,
    )
    ledger.record_trace(run_id="agent-run-001", trace=trace)

    verification = ledger.verify_run("agent-run-001")

    assert verification.trace_count == 1
    assert verification.complete is True
    surface_path = tmp_path / "agent-run-001" / "tool-surface.json"
    surface_path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(AgentTraceTamperDetected, match="tool surface"):
        ledger.verify_run("agent-run-001")
