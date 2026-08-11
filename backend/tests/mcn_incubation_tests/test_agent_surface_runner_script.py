from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcn_incubation.agent_evaluation import AgentTraceLedger
from mcn_incubation.evaluation import load_eval_cases
from mcn_incubation.persistence import IncubationRepository
from mcn_incubation.persistence_schema import bootstrap_incubation_schema
from mcn_incubation.preflight import PreflightLedger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from deerflow.config.app_config import AppConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "run_incubation_agent_eval.py"
CASE_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "incubation-eval-cases.jsonl"
NOW = datetime(2026, 8, 11, 15, 0, tzinfo=UTC)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_incubation_agent_eval", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _case(case_id: str):
    return next(case for case in load_eval_cases(CASE_PATH) if case.case_id == case_id)


def test_agent_eval_prepares_isolated_trials_without_embedding_case_answers() -> None:
    module = _load_script()

    trials = module.prepare_trial_specs(
        cases=(_case("M01"),),
        include_mutations=True,
        run_id="agent-run-001",
    )

    assert [trial.trial_id for trial in trials] == ["M01:initial", "M01:mutation"]
    assert len({trial.project_id for trial in trials}) == 1
    initial_prompt = module.build_agent_eval_prompt(trials[0])
    mutation_prompt = module.build_agent_eval_prompt(trials[1])
    assert trials[0].project_id in initial_prompt
    assert _case("M01").facts[0] not in initial_prompt
    assert "incubation_project_context" not in initial_prompt
    assert "incubation_project_evidence" not in initial_prompt
    assert "信息不足" in initial_prompt
    assert "会改变结论的最少主体信息" in initial_prompt
    assert "不要无依据宣布一种表现形式最适合" in initial_prompt
    assert "不要创建或呈现文件" in initial_prompt
    assert "独立修订轮次" not in mutation_prompt
    assert "结合上一轮实际回答" in mutation_prompt


def test_agent_eval_disables_general_memory_without_mutating_host_config() -> None:
    module = _load_script()
    host_config = AppConfig.model_validate(
        {
            "sandbox": {
                "use": "deerflow.sandbox.local:LocalSandboxProvider",
            },
            "memory": {
                "enabled": True,
                "injection_enabled": True,
            },
        }
    )

    evaluation_config = module.build_agent_eval_app_config(host_config)

    assert evaluation_config is not host_config
    assert evaluation_config.memory.enabled is False
    assert evaluation_config.memory.injection_enabled is False
    assert host_config.memory.enabled is True
    assert host_config.memory.injection_enabled is True


@pytest.mark.asyncio
async def test_agent_eval_seeds_versioned_project_truth_and_evidence(tmp_path) -> None:
    module = _load_script()
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'agent-eval.db'}",
        poolclass=NullPool,
    )
    await bootstrap_incubation_schema(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = IncubationRepository(session_factory)
    initial_trial, mutation_trial = module.prepare_trial_specs(
        cases=(_case("M01"),),
        include_mutations=True,
        run_id="agent-run-001",
    )
    try:
        await module.seed_trial_state(
            repository=repository,
            trial=initial_trial,
            owner_id="agent-eval-owner",
            corpus_sha256=sha256(CASE_PATH.read_bytes()).hexdigest(),
            created_at=NOW,
        )

        initial_truths = await repository.list_current_truths(
            owner_id="agent-eval-owner",
            project_id=initial_trial.project_id,
        )
        initial_evidence = await repository.list_current_evidence(
            owner_id="agent-eval-owner",
            project_id=initial_trial.project_id,
        )

        assert f"新补充证据：{_case('M01').mutation}" not in {truth.statement for truth in initial_truths}
        assert len(initial_evidence) == 1

        await module.append_trial_mutation(
            repository=repository,
            trial=mutation_trial,
            owner_id="agent-eval-owner",
            corpus_sha256=sha256(CASE_PATH.read_bytes()).hexdigest(),
            created_at=NOW,
        )

        truths = await repository.list_current_truths(
            owner_id="agent-eval-owner",
            project_id=mutation_trial.project_id,
        )
        evidence = await repository.list_current_evidence(
            owner_id="agent-eval-owner",
            project_id=mutation_trial.project_id,
        )

        statements = {truth.statement for truth in truths}
        assert _case("M01").scenario in statements
        assert all(fact in statements for fact in _case("M01").facts)
        assert all(f"现实限制：{value}" in statements for value in _case("M01").constraints)
        assert all(f"经营目标：{value}" in statements for value in _case("M01").goals)
        assert all(f"当前产品或服务：{value}" in statements for value in _case("M01").offers)
        assert f"新补充证据：{_case('M01').mutation}" in statements
        assert len(evidence) == 2
        evidence_by_locator = {item.source_locator: item for item in evidence}
        initial_item = evidence_by_locator["eval-corpus://incubation-eval-cases/M01"]
        mutation_item = evidence_by_locator["eval-corpus://incubation-eval-cases/M01#mutation"]
        assert "不是账号实际经营结果" in initial_item.limitations[0]
        assert "不是账号实际经营结果" in mutation_item.limitations[0]
    finally:
        await engine.dispose()


def test_agent_eval_requires_explicit_trial_and_step_caps() -> None:
    module = _load_script()

    with pytest.raises(SystemExit):
        module._parse_args(["--case", "M01", "--max-paid-trials", "1"])
    with pytest.raises(SystemExit):
        module._parse_args(
            [
                "--case",
                "M01",
                "--max-paid-trials",
                "1",
                "--max-agent-steps",
                "100",
                "--execute",
            ]
        )

    with pytest.raises(SystemExit):
        module._parse_args(
            [
                "--case",
                "M01",
                "--max-paid-trials",
                "1",
                "--max-agent-steps",
                "12",
                "--max-model-calls",
                "6",
                "--execute",
            ]
        )
    with pytest.raises(SystemExit):
        module._parse_args(
            [
                "--case",
                "M01",
                "--max-paid-trials",
                "1",
                "--max-agent-steps",
                "100",
                "--max-model-calls",
                "0",
                "--execute",
            ]
        )

    args = module._parse_args(
        [
            "--case",
            "M01",
            "--max-paid-trials",
            "1",
            "--max-agent-steps",
            "100",
            "--max-model-calls",
            "6",
            "--execute",
        ]
    )
    assert args.case_ids == ["M01"]
    assert args.max_paid_trials == 1
    assert args.max_agent_steps == 100
    assert args.max_model_calls == 6
    module.enforce_paid_trial_cap(trial_count=1, max_paid_trials=1)
    with pytest.raises(ValueError, match="paid trial cap"):
        module.enforce_paid_trial_cap(trial_count=2, max_paid_trials=1)


def test_agent_eval_model_call_budget_is_hard_and_per_run() -> None:
    module = _load_script()
    budget = module.EvaluationModelCallBudget(max_calls=2)

    assert budget.reserve(("thread-a", "run-a")) is True
    assert budget.reserve(("thread-a", "run-a")) is True
    assert budget.reserve(("thread-a", "run-a")) is False
    assert budget.reserve(("thread-a", "run-b")) is True
    fallback = budget._fallback()
    assert fallback.result[0].additional_kwargs == {
        "deerflow_error_fallback": True,
        "error_reason": "evaluation_model_call_cap_reached",
    }


def test_agent_eval_uses_existing_deerflow_lead_agent_runtime() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "DeerFlowClient" in source
    assert "InMemorySaver" in source
    assert "subagent_enabled=False" in source
    assert "create_chat_model" not in source
    assert "create_react_agent" not in source
    assert "create_agent(" not in source


def test_agent_eval_main_seals_full_offline_run_with_fake_stream(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_script()

    class FakeClient:
        calls = []

        def __init__(self, **kwargs):
            assert len(kwargs["middlewares"]) == 1
            assert kwargs["middlewares"][0].max_calls == 6
            assert kwargs["app_config"].memory.enabled is False
            assert kwargs["app_config"].memory.injection_enabled is False

        def list_models(self):
            return {"models": [{"name": "fake-model"}]}

        @staticmethod
        def _get_tools(*, model_name, subagent_enabled):
            assert model_name == "fake-model"
            assert subagent_enabled is False
            from deerflow.tools.builtins import (
                incubation_context_tool,
                incubation_project_context_tool,
                incubation_project_evidence_tool,
            )

            return [
                incubation_context_tool,
                incubation_project_context_tool,
                incubation_project_evidence_tool,
            ]

        def stream(self, prompt, *, thread_id, **kwargs):
            self.calls.append((prompt, thread_id))
            assert "agent-eval-offline-M01" in prompt
            assert thread_id
            assert kwargs["user_id"].startswith("agent-eval-owner-")
            assert kwargs["recursion_limit"] == 100
            yield SimpleNamespace(
                type="messages-tuple",
                data={
                    "type": "ai",
                    "id": "tools",
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "incubation_project_context",
                            "id": "call-1",
                            "args": {"project_id": "agent-eval-offline-M01"},
                        }
                    ],
                },
            )
            yield SimpleNamespace(
                type="messages-tuple",
                data={
                    "type": "tool",
                    "name": "incubation_project_context",
                    "tool_call_id": "call-1",
                    "content": '{"authority":"project_truth_ledger","truths":[]}',
                },
            )
            yield SimpleNamespace(
                type="messages-tuple",
                data={"type": "ai", "id": "final", "content": "离线孵化判断"},
            )
            yield SimpleNamespace(
                type="end",
                data={
                    "usage": {
                        "input_tokens": 50,
                        "output_tokens": 20,
                        "total_tokens": 70,
                    }
                },
            )

    monkeypatch.setattr(module, "DeerFlowClient", FakeClient)
    output_root = tmp_path / "agent-eval-output"

    result = module.main(
        [
            "--case",
            "M01",
            "--include-mutations",
            "--max-paid-trials",
            "2",
            "--max-agent-steps",
            "100",
            "--max-model-calls",
            "6",
            "--model",
            "fake-model",
            "--run-id",
            "offline",
            "--output-root",
            str(output_root),
            "--execute",
        ]
    )

    assert result == 0
    assert len(FakeClient.calls) == 2
    assert FakeClient.calls[0][1] == FakeClient.calls[1][1]
    assert "结合上一轮实际回答" in FakeClient.calls[1][0]
    assert PreflightLedger(output_root).verify_run("offline").completed is True
    assert AgentTraceLedger(output_root).verify_run("offline").complete is True
    run_dir = output_root / "offline"
    assert (run_dir / "agent-state.db").is_file()
    assert (run_dir / "agent-state.db.sha256").is_file()
    prompt = (run_dir / "inputs" / "M01_initial.txt").read_text(encoding="utf-8")
    assert _case("M01").facts[0] not in prompt
    initial_trace = json.loads((run_dir / "traces" / "M01_initial.json").read_text(encoding="utf-8"))
    mutation_trace = json.loads((run_dir / "traces" / "M01_mutation.json").read_text(encoding="utf-8"))
    assert "incubation_project_context" in json.dumps(initial_trace)
    assert initial_trace["project_id"] == mutation_trace["project_id"]
    assert initial_trace["thread_id"] == mutation_trace["thread_id"]
