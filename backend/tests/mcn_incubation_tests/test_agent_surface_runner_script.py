from __future__ import annotations

import importlib.util
import json
import re
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
CONTENT_WORLD_CASE_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "content-world-production-eval-cases.jsonl"
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


def test_agent_eval_content_world_mode_uses_the_original_request_without_full_delivery_pressure() -> None:
    module = _load_script()
    cases = load_eval_cases(CONTENT_WORLD_CASE_PATH)
    trials = module.prepare_trial_specs(
        cases=cases,
        include_mutations=False,
        run_id="content-world-production",
    )

    assert [case.case_id for case in cases] == ["CW01-gold-gift", "CW02-fruit-world"]
    for case, trial in zip(cases, trials, strict=True):
        prompt = module.build_agent_eval_prompt(
            trial,
            task_mode=module.AgentEvalTaskMode.CONTENT_WORLD,
        )
        assert trial.project_id in prompt
        assert case.scenario in prompt
        assert "只要求先打开这个商业对象的起号思路" in prompt
        assert "表现形式、持续内容、变现与转化问题" not in prompt
        assert "会改变结论的最少主体信息" not in prompt
        assert "不要无依据宣布一种表现形式最适合" not in prompt
        for leaked_answer in ("礼品是品类中心", "人情世界", "水果本身是", "榴莲"):
            assert leaked_answer not in prompt


def test_agent_eval_bounds_generated_thread_ids_without_merging_cases() -> None:
    module = _load_script()
    run_id = "agent-eval-content-world-production-v2-20260811"

    gold = module.build_trial_thread_id(run_id=run_id, case_id="CW01-gold-gift")
    fruit = module.build_trial_thread_id(run_id=run_id, case_id="CW02-fruit-world")

    assert len(gold) <= 64
    assert len(fruit) <= 64
    assert re.fullmatch(r"[A-Za-z0-9_-]+", gold)
    assert re.fullmatch(r"[A-Za-z0-9_-]+", fruit)
    assert gold != fruit
    assert gold == module.build_trial_thread_id(run_id=run_id, case_id="CW01-gold-gift")

    dotted = module.build_trial_thread_id(run_id="agent.eval.v2", case_id="CW.01")
    assert re.fullmatch(r"[A-Za-z0-9_-]+", dotted)


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


def test_agent_eval_evidence_research_mode_is_read_only_and_run_scoped() -> None:
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
            "subagents": {
                "max_total_per_run": 6,
                "custom_agents": {
                    "host-agent": {
                        "description": "Host custom role",
                        "system_prompt": "Host custom prompt",
                    }
                },
            },
        }
    )

    evaluation_config = module.build_agent_eval_app_config(
        host_config,
        subagent_mode="evidence-review",
        max_subagent_steps=50,
        max_subagent_tokens=30_000,
    )

    specialist_name = module.INCUBATION_EVIDENCE_RESEARCHER_NAME
    specialist = evaluation_config.subagents.custom_agents[specialist_name]
    specialist_budget = evaluation_config.subagents.agents[specialist_name].token_budget
    assert evaluation_config.subagents.allowed_agents == [specialist_name]
    assert evaluation_config.subagents.max_total_per_run == 1
    assert set(evaluation_config.subagents.custom_agents) == {specialist_name}
    assert specialist.tools == sorted(module._REQUIRED_INCUBATION_READ_TOOLS)
    assert "incubation_record_subject_answer" in module._REQUIRED_INCUBATION_LEAD_TOOLS
    assert "incubation_record_subject_answer" not in specialist.tools
    assert specialist.disallowed_tools == [
        "task",
        "ask_clarification",
        "present_files",
        "incubation_record_subject_answer",
    ]
    assert specialist.skills == []
    assert specialist.max_turns == 50
    assert specialist.timeout_seconds == 120
    assert specialist_budget is not None
    assert specialist_budget.enabled is True
    assert specialist_budget.max_tokens == 30_000
    assert "最终孵化判断" in specialist.system_prompt
    assert "不得修改" in specialist.system_prompt
    assert "支持事实与证据" in specialist.system_prompt
    assert "会反转判断的未知" in specialist.system_prompt
    assert "无依据假设" in specialist.system_prompt
    from deerflow.agents.lead_agent.prompt import apply_prompt_template

    rendered_prompt = apply_prompt_template(
        subagent_enabled=True,
        max_concurrent_subagents=1,
        max_total_subagents=1,
        app_config=evaluation_config,
        available_skills=set(),
    )
    assert f"- **{specialist_name}**:" in rendered_prompt
    assert "- **general-purpose**:" not in rendered_prompt
    assert "- **bash**:" not in rendered_prompt
    assert host_config.subagents.max_total_per_run == 6
    assert set(host_config.subagents.custom_agents) == {"host-agent"}


def test_agent_eval_incubation_team_has_five_read_only_board_specialists() -> None:
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
            "subagents": {
                "max_total_per_run": 6,
                "custom_agents": {
                    "host-agent": {
                        "description": "Host custom role",
                        "system_prompt": "Host custom prompt",
                    }
                },
            },
        }
    )

    evaluation_config = module.build_agent_eval_app_config(
        host_config,
        subagent_mode="incubation-team",
        max_subagent_steps=40,
        max_subagent_tokens=12_000,
    )

    expected_names = (
        "incubation-positioning-specialist",
        "incubation-audience-specialist",
        "incubation-content-specialist",
        "incubation-expression-specialist",
        "incubation-commercial-specialist",
    )
    assert module.INCUBATION_TEAM_SPECIALIST_NAMES == expected_names
    assert evaluation_config.subagents.allowed_agents == list(expected_names)
    assert evaluation_config.subagents.max_total_per_run == len(expected_names)
    assert set(evaluation_config.subagents.custom_agents) == set(expected_names)
    assert set(evaluation_config.subagents.agents) == set(expected_names)

    for name in expected_names:
        specialist = evaluation_config.subagents.custom_agents[name]
        budget = evaluation_config.subagents.agents[name].token_budget
        assert specialist.tools == [
            "incubation_project_context",
            "incubation_project_evidence",
        ]
        assert specialist.disallowed_tools == [
            "task",
            "ask_clarification",
            "present_files",
            "incubation_record_subject_answer",
        ]
        assert specialist.skills == []
        assert specialist.model == "inherit"
        assert specialist.max_turns == 40
        assert specialist.timeout_seconds == 120
        assert budget is not None
        assert budget.enabled is True
        assert budget.max_tokens == 12_000
        assert "不直接面向用户" in specialist.system_prompt
        assert "最终整合" in specialist.system_prompt
        assert "最强反证" in specialist.system_prompt
        assert "不得补造" in specialist.system_prompt

    positioning = evaluation_config.subagents.custom_agents[expected_names[0]].system_prompt
    audience = evaluation_config.subagents.custom_agents[expected_names[1]].system_prompt
    content = evaluation_config.subagents.custom_agents[expected_names[2]].system_prompt
    expression = evaluation_config.subagents.custom_agents[expected_names[3]].system_prompt
    commercial = evaluation_config.subagents.custom_agents[expected_names[4]].system_prompt
    assert "IP 主体" in positioning and "赛道" in positioning and "人设" in positioning
    assert "受众假设" in audience and "实际受众证据" in audience
    assert "内容世界" in content and "历史故事" in content
    assert "表现形式" in expression and "口播" in expression and "默认" in expression
    assert "历史故事不是表现形式" in expression
    assert "变现" in commercial and "信任" in commercial and "成交" in commercial

    from deerflow.agents.lead_agent.prompt import apply_prompt_template

    rendered_prompt = apply_prompt_template(
        subagent_enabled=True,
        max_concurrent_subagents=3,
        max_total_subagents=5,
        app_config=evaluation_config,
        available_skills=set(),
    )
    for name in expected_names:
        assert f"- **{name}**:" in rendered_prompt
    assert "- **general-purpose**:" not in rendered_prompt
    assert "- **bash**:" not in rendered_prompt

    assert host_config.subagents.max_total_per_run == 6
    assert set(host_config.subagents.custom_agents) == {"host-agent"}


def test_agent_eval_team_prompt_requires_parallel_board_work_and_lead_synthesis() -> None:
    module = _load_script()
    trial = module.prepare_trial_specs(
        cases=(_case("M01"),),
        include_mutations=False,
        run_id="incubation-team-offline",
    )[0]

    prompt = module.build_agent_eval_prompt(
        trial,
        subagent_mode="incubation-team",
    )

    for name in module.INCUBATION_TEAM_SPECIALIST_NAMES:
        assert name in prompt
    assert "每个专业子 Agent 恰好委派一次" in prompt
    assert "独立板块尽量并行" in prompt
    assert "不是线性阶段" in prompt
    assert "分批只是技术并发限制" in prompt
    assert "先委派三个" not in prompt
    assert "不得投票" in prompt
    assert "不得打分" in prompt
    assert "不得直接拼接" in prompt
    assert "内容与表现形式是两个不同板块" in prompt
    assert "只有 Lead" in prompt
    assert _case("M01").facts[0] not in prompt


def test_agent_eval_team_system_hash_covers_every_specialist_and_concurrency(monkeypatch) -> None:
    module = _load_script()
    host_config = AppConfig.model_validate(
        {
            "sandbox": {
                "use": "deerflow.sandbox.local:LocalSandboxProvider",
            },
        }
    )
    evaluation_config = module.build_agent_eval_app_config(
        host_config,
        subagent_mode="incubation-team",
        max_subagent_steps=40,
        max_subagent_tokens=12_000,
    )
    baseline_hash = module._evaluation_system_contract_sha256(
        app_config=evaluation_config,
        subagent_mode="incubation-team",
    )

    specialist_name = module.INCUBATION_TEAM_SPECIALIST_NAMES[2]
    changed_agents = dict(evaluation_config.subagents.custom_agents)
    changed_agents[specialist_name] = changed_agents[specialist_name].model_copy(update={"system_prompt": changed_agents[specialist_name].system_prompt + "\nchanged"})
    changed_subagents = evaluation_config.subagents.model_copy(update={"custom_agents": changed_agents})
    changed_config = evaluation_config.model_copy(update={"subagents": changed_subagents})
    assert (
        module._evaluation_system_contract_sha256(
            app_config=changed_config,
            subagent_mode="incubation-team",
        )
        != baseline_hash
    )

    monkeypatch.setattr(module, "_INCUBATION_TEAM_MAX_CONCURRENT", 2)
    assert (
        module._evaluation_system_contract_sha256(
            app_config=evaluation_config,
            subagent_mode="incubation-team",
        )
        != baseline_hash
    )


def test_agent_eval_team_protocol_accepts_each_role_once_in_any_order() -> None:
    module = _load_script()
    shuffled_names = (
        module.INCUBATION_TEAM_SPECIALIST_NAMES[3],
        module.INCUBATION_TEAM_SPECIALIST_NAMES[1],
        module.INCUBATION_TEAM_SPECIALIST_NAMES[4],
        module.INCUBATION_TEAM_SPECIALIST_NAMES[0],
        module.INCUBATION_TEAM_SPECIALIST_NAMES[2],
    )
    events = []
    for index, name in enumerate(shuffled_names, start=1):
        events.append(
            SimpleNamespace(
                event_type="tool_call",
                tool_name="task",
                tool_call_id=f"task-{index}",
                arguments={
                    "subagent_type": name,
                    "prompt": "Read project project-001 and return a board brief.",
                },
            )
        )
        events.append(
            SimpleNamespace(
                event_type="tool_result",
                tool_name="task",
                tool_call_id=f"task-{index}",
                arguments=None,
            )
        )

    task_statuses = {f"task-{index}": "completed" for index in range(1, 6)}
    assert (
        module._incubation_team_protocol_error(
            events,
            task_statuses=task_statuses,
            project_id="project-001",
        )
        is None
    )


def test_agent_eval_team_protocol_requires_completed_tasks_and_project_binding() -> None:
    module = _load_script()
    events = []
    for index, name in enumerate(module.INCUBATION_TEAM_SPECIALIST_NAMES, start=1):
        events.extend(
            (
                SimpleNamespace(
                    event_type="tool_call",
                    tool_name="task",
                    tool_call_id=f"task-{index}",
                    arguments={
                        "subagent_type": name,
                        "prompt": "Read project project-001 and return a board brief.",
                    },
                ),
                SimpleNamespace(
                    event_type="tool_result",
                    tool_name="task",
                    tool_call_id=f"task-{index}",
                    arguments=None,
                ),
            )
        )

    statuses = {f"task-{index}": "completed" for index in range(1, 6)}
    statuses["task-3"] = "failed"
    assert (
        module._incubation_team_protocol_error(
            events,
            task_statuses=statuses,
            project_id="project-001",
        )
        == "incubation_team_task_not_completed"
    )

    statuses["task-3"] = "completed"
    events[0].arguments["prompt"] = "Return a positioning brief."
    assert (
        module._incubation_team_protocol_error(
            events,
            task_statuses=statuses,
            project_id="project-001",
        )
        == "incubation_team_unbound_project"
    )


@pytest.mark.parametrize(
    ("names", "include_results", "expected_error"),
    [
        (
            (
                "incubation-positioning-specialist",
                "incubation-audience-specialist",
                "incubation-content-specialist",
                "incubation-expression-specialist",
            ),
            True,
            "incubation_team_missing_specialist",
        ),
        (
            (
                "incubation-positioning-specialist",
                "incubation-positioning-specialist",
                "incubation-content-specialist",
                "incubation-expression-specialist",
                "incubation-commercial-specialist",
            ),
            True,
            "incubation_team_duplicate_specialist",
        ),
        (
            (
                "incubation-positioning-specialist",
                "incubation-audience-specialist",
                "incubation-content-specialist",
                "incubation-expression-specialist",
                "unknown-specialist",
            ),
            True,
            "incubation_team_unknown_specialist",
        ),
        (
            (
                "incubation-positioning-specialist",
                "incubation-audience-specialist",
                "incubation-content-specialist",
                "incubation-expression-specialist",
                "incubation-commercial-specialist",
            ),
            False,
            "incubation_team_missing_task_result",
        ),
    ],
)
def test_agent_eval_team_protocol_rejects_invalid_delegation_traces(
    names,
    include_results,
    expected_error,
) -> None:
    module = _load_script()
    events = []
    for index, name in enumerate(names, start=1):
        events.append(
            SimpleNamespace(
                event_type="tool_call",
                tool_name="task",
                tool_call_id=f"task-{index}",
                arguments={
                    "subagent_type": name,
                    "prompt": "Read project project-001 and return a board brief.",
                },
            )
        )
        if include_results:
            events.append(
                SimpleNamespace(
                    event_type="tool_result",
                    tool_name="task",
                    tool_call_id=f"task-{index}",
                    arguments=None,
                )
            )

    task_statuses = {f"task-{index}": "completed" for index in range(1, len(names) + 1)}
    assert (
        module._incubation_team_protocol_error(
            events,
            task_statuses=task_statuses,
            project_id="project-001",
        )
        == expected_error
    )


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
                "100",
                "--max-model-calls",
                "4",
                "--task-mode",
                "content_world",
                "--method-context-mode",
                "disabled",
                "--subagent-mode",
                "evidence-review",
                "--max-subagent-steps",
                "50",
                "--max-subagent-tokens",
                "30000",
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
    assert args.task_mode == "full_incubation"
    assert args.method_context_mode == "available"
    content_world_args = module._parse_args(
        [
            "--case",
            "CW01-gold-gift",
            "--max-paid-trials",
            "1",
            "--max-agent-steps",
            "100",
            "--max-model-calls",
            "4",
            "--task-mode",
            "content_world",
            "--method-context-mode",
            "disabled",
            "--execute",
        ]
    )
    assert content_world_args.task_mode == "content_world"
    assert content_world_args.method_context_mode == "disabled"
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
                "4",
                "--method-context-mode",
                "disabled",
                "--execute",
            ]
        )
    module.enforce_paid_trial_cap(trial_count=1, max_paid_trials=1)
    with pytest.raises(ValueError, match="paid trial cap"):
        module.enforce_paid_trial_cap(trial_count=2, max_paid_trials=1)


def test_agent_eval_requires_separate_subagent_caps_for_evidence_mode() -> None:
    module = _load_script()
    common = [
        "--case",
        "M01",
        "--max-paid-trials",
        "1",
        "--max-agent-steps",
        "100",
        "--max-model-calls",
        "6",
        "--subagent-mode",
        "evidence-review",
        "--execute",
    ]

    with pytest.raises(SystemExit):
        module._parse_args(common)
    with pytest.raises(SystemExit):
        module._parse_args([*common, "--max-subagent-steps", "50"])
    with pytest.raises(SystemExit):
        module._parse_args(
            [
                *common,
                "--max-subagent-steps",
                "8",
                "--max-subagent-tokens",
                "30000",
            ]
        )

    args = module._parse_args(
        [
            *common,
            "--max-subagent-steps",
            "50",
            "--max-subagent-tokens",
            "30000",
        ]
    )
    assert args.subagent_mode == "evidence-review"
    assert args.max_subagent_steps == 50
    assert args.max_subagent_tokens == 30_000


def test_agent_eval_accepts_only_capped_full_incubation_team_trials() -> None:
    module = _load_script()
    common = [
        "--case",
        "M01",
        "--max-paid-trials",
        "1",
        "--max-agent-steps",
        "100",
        "--max-model-calls",
        "8",
        "--subagent-mode",
        "incubation-team",
        "--max-subagent-steps",
        "40",
        "--max-subagent-tokens",
        "12000",
        "--execute",
    ]

    args = module._parse_args(common)
    assert args.subagent_mode == "incubation-team"
    assert args.task_mode == "full_incubation"

    with pytest.raises(SystemExit):
        module._parse_args([*common, "--task-mode", "content_world"])
    with pytest.raises(SystemExit):
        module._parse_args(
            [
                *common,
                "--method-context-mode",
                "distilled_user_reasoning",
            ]
        )


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
    assert "create_chat_model" not in source
    assert "create_react_agent" not in source
    assert "create_agent(" not in source


def test_agent_eval_can_remove_method_context_from_only_the_evaluation_tool_surface(monkeypatch) -> None:
    module = _load_script()

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        @staticmethod
        def _get_tools(*, model_name, subagent_enabled):
            assert model_name == "fake-model"
            assert subagent_enabled is False
            return [
                SimpleNamespace(name="incubation_context"),
                SimpleNamespace(name="incubation_project_context"),
            ]

    monkeypatch.setattr(module, "DeerFlowClient", FakeClient)

    available = module.build_agent_eval_client(
        method_context_mode=module.MethodContextMode.AVAILABLE,
    )
    disabled = module.build_agent_eval_client(
        method_context_mode=module.MethodContextMode.DISABLED,
    )
    distilled = module.build_agent_eval_client(
        method_context_mode=module.MethodContextMode.DISTILLED_USER_REASONING,
    )

    assert [tool.name for tool in available._get_tools(model_name="fake-model", subagent_enabled=False)] == [
        "incubation_context",
        "incubation_project_context",
    ]
    assert [tool.name for tool in disabled._get_tools(model_name="fake-model", subagent_enabled=False)] == ["incubation_project_context"]
    distilled_tools = distilled._get_tools(model_name="fake-model", subagent_enabled=False)
    assert [tool.name for tool in distilled_tools] == [
        "incubation_project_context",
        "incubation_context",
    ]
    distilled_payload = distilled_tools[-1].invoke({"query": "打开一个陌生商业对象的内容世界", "limit": 4})
    assert distilled_payload["authority"] == "evaluation_hypothesis_only"
    assert distilled_payload["method_card"]["method_card_id"] == "user-distilled-incubation-v1"
    assert "content-engine-v1" not in json.dumps(distilled_payload, ensure_ascii=False)


def test_agent_eval_limits_distilled_user_reasoning_to_isolated_content_world_trials() -> None:
    module = _load_script()
    common = [
        "--case",
        "CW01-gold-gift",
        "--max-paid-trials",
        "1",
        "--max-agent-steps",
        "100",
        "--max-model-calls",
        "4",
        "--method-context-mode",
        "distilled_user_reasoning",
        "--execute",
    ]

    args = module._parse_args([*common, "--task-mode", "content_world"])
    assert args.method_context_mode == "distilled_user_reasoning"

    with pytest.raises(SystemExit):
        module._parse_args(common)
    with pytest.raises(SystemExit):
        module._parse_args(
            [
                *common,
                "--task-mode",
                "content_world",
                "--subagent-mode",
                "evidence-review",
                "--max-subagent-steps",
                "50",
                "--max-subagent-tokens",
                "30000",
            ]
        )


def test_agent_eval_main_seals_content_world_ablation_with_fake_stream(
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
                incubation_record_subject_answer_tool,
            )

            return [
                incubation_context_tool,
                incubation_project_context_tool,
                incubation_project_evidence_tool,
                incubation_record_subject_answer_tool,
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
            "--task-mode",
            "content_world",
            "--method-context-mode",
            "disabled",
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
    experiment = json.loads((run_dir / "experiment.json").read_text(encoding="utf-8"))
    assert experiment["task_mode"] == "content_world"
    assert experiment["method_context_mode"] == "disabled"
    tool_surface = json.loads((run_dir / "tool-surface.json").read_text(encoding="utf-8"))
    assert "incubation_context" not in {tool["function"]["name"] for tool in tool_surface}


def test_agent_eval_main_can_seal_bounded_evidence_subagent_trial(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_script()

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["subagent_enabled"] is True
            config = kwargs["app_config"]
            assert config.subagents.allowed_agents == [module.INCUBATION_EVIDENCE_RESEARCHER_NAME]
            assert config.subagents.max_total_per_run == 1

        def list_models(self):
            return {"models": [{"name": "fake-model"}]}

        @staticmethod
        def _get_tools(*, model_name, subagent_enabled):
            assert model_name == "fake-model"
            assert subagent_enabled is True
            from deerflow.tools.builtins import (
                incubation_context_tool,
                incubation_project_context_tool,
                incubation_project_evidence_tool,
                incubation_record_subject_answer_tool,
                task_tool,
            )

            return [
                incubation_context_tool,
                incubation_project_context_tool,
                incubation_project_evidence_tool,
                incubation_record_subject_answer_tool,
                task_tool,
            ]

        def stream(self, prompt, *, thread_id, **kwargs):
            assert kwargs["recursion_limit"] == 100
            yield SimpleNamespace(
                type="messages-tuple",
                data={
                    "type": "ai",
                    "id": "delegate",
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "task",
                            "id": "task-1",
                            "args": {
                                "description": "review project evidence",
                                "prompt": "Return a bounded evidence brief for the project.",
                                "subagent_type": module.INCUBATION_EVIDENCE_RESEARCHER_NAME,
                            },
                        }
                    ],
                },
            )
            yield SimpleNamespace(
                type="messages-tuple",
                data={
                    "type": "tool",
                    "name": "task",
                    "tool_call_id": "task-1",
                    "content": "Task completed. Result: facts and unknowns only",
                },
            )
            yield SimpleNamespace(
                type="messages-tuple",
                data={"type": "ai", "id": "final", "content": "Lead的条件化孵化判断"},
            )
            yield SimpleNamespace(
                type="end",
                data={"usage": {"input_tokens": 90, "output_tokens": 30, "total_tokens": 120}},
            )

    monkeypatch.setattr(module, "DeerFlowClient", FakeClient)
    output_root = tmp_path / "multiagent-eval-output"

    result = module.main(
        [
            "--case",
            "M01",
            "--max-paid-trials",
            "1",
            "--max-agent-steps",
            "100",
            "--max-model-calls",
            "6",
            "--subagent-mode",
            "evidence-review",
            "--max-subagent-steps",
            "50",
            "--max-subagent-tokens",
            "30000",
            "--model",
            "fake-model",
            "--run-id",
            "offline-multiagent",
            "--output-root",
            str(output_root),
            "--execute",
        ]
    )

    assert result == 0
    run_dir = output_root / "offline-multiagent"
    experiment = json.loads((run_dir / "experiment.json").read_text(encoding="utf-8"))
    assert experiment["subagent_mode"] == "evidence-review"
    assert experiment["decision_authority"] == "lead-agent"
    assert experiment["allowed_subagents"] == [module.INCUBATION_EVIDENCE_RESEARCHER_NAME]
    assert experiment["max_total_delegations"] == 1
    assert experiment["max_subagent_steps"] == 50
    assert experiment["max_subagent_tokens"] == 30_000
    assert experiment["task_mode"] == "full_incubation"
    assert experiment["method_context_mode"] == "available"
    assert (run_dir / "experiment.json.sha256").is_file()
    trace = json.loads((run_dir / "traces" / "M01_initial.json").read_text(encoding="utf-8"))
    task_calls = [event for event in trace["events"] if event["tool_name"] == "task" and event["event_type"] == "tool_call"]
    assert task_calls[0]["arguments"]["subagent_type"] == module.INCUBATION_EVIDENCE_RESEARCHER_NAME


def test_agent_eval_main_seals_five_specialist_team_and_exact_delegations(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_script()

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["subagent_enabled"] is True
            config = kwargs["app_config"]
            assert config.subagents.allowed_agents == list(module.INCUBATION_TEAM_SPECIALIST_NAMES)
            assert config.subagents.max_total_per_run == 5

        def list_models(self):
            return {"models": [{"name": "fake-model"}]}

        @staticmethod
        def _get_tools(*, model_name, subagent_enabled):
            assert model_name == "fake-model"
            assert subagent_enabled is True
            from deerflow.tools.builtins import (
                incubation_context_tool,
                incubation_project_context_tool,
                incubation_project_evidence_tool,
                incubation_record_subject_answer_tool,
                task_tool,
            )

            return [
                incubation_context_tool,
                incubation_project_context_tool,
                incubation_project_evidence_tool,
                incubation_record_subject_answer_tool,
                task_tool,
            ]

        def stream(self, prompt, *, thread_id, **kwargs):
            assert "每个专业子 Agent 恰好委派一次" in prompt
            assert kwargs["recursion_limit"] == 100
            assert kwargs["max_concurrent_subagents"] == 3
            assert kwargs["max_total_subagents"] == 5
            names = module.INCUBATION_TEAM_SPECIALIST_NAMES
            batches = ((names[1], names[0], names[2]), (names[4], names[3]))
            call_number = 0
            for batch_number, names in enumerate(batches, start=1):
                calls = []
                for name in names:
                    call_number += 1
                    calls.append(
                        {
                            "name": "task",
                            "id": f"task-{call_number}",
                            "args": {
                                "description": f"review {name} board",
                                "prompt": "Read project agent-eval-offline-incubation-team-M01 and return only your bounded board brief.",
                                "subagent_type": name,
                            },
                        }
                    )
                yield SimpleNamespace(
                    type="messages-tuple",
                    data={
                        "type": "ai",
                        "id": f"delegate-{batch_number}",
                        "content": "",
                        "tool_calls": calls,
                    },
                )
                for call in calls:
                    yield SimpleNamespace(
                        type="custom",
                        data={
                            "type": "task_completed",
                            "task_id": call["id"],
                            "usage": {
                                "input_tokens": 20,
                                "output_tokens": 10,
                                "total_tokens": 30,
                            },
                        },
                    )
                    yield SimpleNamespace(
                        type="messages-tuple",
                        data={
                            "type": "tool",
                            "name": "task",
                            "tool_call_id": call["id"],
                            "content": f"Task completed. Result: {call['args']['subagent_type']} brief",
                        },
                    )
            yield SimpleNamespace(
                type="messages-tuple",
                data={"type": "ai", "id": "final", "content": "Lead综合后的单一孵化判断"},
            )
            yield SimpleNamespace(
                type="end",
                data={"usage": {"input_tokens": 300, "output_tokens": 100, "total_tokens": 400}},
            )

    monkeypatch.setattr(module, "DeerFlowClient", FakeClient)
    output_root = tmp_path / "incubation-team-output"

    result = module.main(
        [
            "--case",
            "M01",
            "--max-paid-trials",
            "1",
            "--max-agent-steps",
            "100",
            "--max-model-calls",
            "8",
            "--subagent-mode",
            "incubation-team",
            "--max-subagent-steps",
            "40",
            "--max-subagent-tokens",
            "12000",
            "--model",
            "fake-model",
            "--run-id",
            "offline-incubation-team",
            "--output-root",
            str(output_root),
            "--execute",
        ]
    )

    assert result == 0
    run_dir = output_root / "offline-incubation-team"
    experiment = json.loads((run_dir / "experiment.json").read_text(encoding="utf-8"))
    assert experiment["subagent_mode"] == "incubation-team"
    assert experiment["decision_authority"] == "lead-agent"
    assert experiment["allowed_subagents"] == list(module.INCUBATION_TEAM_SPECIALIST_NAMES)
    assert experiment["max_total_delegations"] == 5
    assert experiment["max_concurrent_subagents"] == 3
    assert experiment["max_subagent_steps"] == 40
    assert experiment["max_subagent_tokens"] == 12_000
    trace = json.loads((run_dir / "traces" / "M01_initial.json").read_text(encoding="utf-8"))
    task_calls = [event for event in trace["events"] if event["tool_name"] == "task" and event["event_type"] == "tool_call"]
    called_roles = [event["arguments"]["subagent_type"] for event in task_calls]
    assert set(called_roles) == set(module.INCUBATION_TEAM_SPECIALIST_NAMES)
    assert len(called_roles) == len(set(called_roles)) == 5
