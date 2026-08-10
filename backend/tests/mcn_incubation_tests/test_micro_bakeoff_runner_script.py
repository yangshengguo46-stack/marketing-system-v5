from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcn_incubation.context import ArchitectureVariant
from mcn_incubation.evaluation import load_eval_cases
from mcn_incubation.methods import default_method_cards

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "run_incubation_micro_bakeoff.py"
CASE_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "incubation-eval-cases.jsonl"
NOW = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_incubation_micro_bakeoff", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _case(case_id: str):
    return next(case for case in load_eval_cases(CASE_PATH) if case.case_id == case_id)


def test_prepare_trials_builds_distinct_contexts_under_one_budget() -> None:
    module = _load_script()
    variants = (
        ArchitectureVariant.V4_FIXED_WORKFLOW,
        ArchitectureVariant.LONG_PROMPT_FULL_HANDBOOK,
        ArchitectureVariant.THIN_PROMPT_ON_DEMAND_METHODS,
        ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH,
    )

    trials = module.prepare_trials(
        cases=(_case("B01"),),
        variants=variants,
        context_budget_chars=12_000,
        seed=17,
        created_at=NOW,
    )

    assert len(trials) == 4
    assert {trial.variant for trial in trials} == set(variants)
    assert len({trial.trial_id for trial in trials}) == 4
    assert all(trial.bundle.estimated_chars <= 12_000 for trial in trials)
    by_variant = {trial.variant: trial for trial in trials}
    assert by_variant[ArchitectureVariant.V4_FIXED_WORKFLOW].bundle.fixed_workflow
    assert len(by_variant[ArchitectureVariant.LONG_PROMPT_FULL_HANDBOOK].bundle.method_cards) == len(default_method_cards())
    assert 1 <= len(by_variant[ArchitectureVariant.THIN_PROMPT_ON_DEMAND_METHODS].bundle.method_cards) <= 3
    assert by_variant[ArchitectureVariant.THIN_PROMPT_ON_DEMAND_METHODS].bundle.truths == ()
    assert by_variant[ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH].bundle.truths
    assert all("请直接给出最终孵化判断" in trial.user_message for trial in trials)


def test_micro_runner_refuses_unreviewed_case_memory_and_trial_cap_overflow() -> None:
    module = _load_script()

    with pytest.raises(ValueError, match="reviewed case memory"):
        module.prepare_trials(
            cases=(_case("B01"),),
            variants=(ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH_CASES,),
            context_budget_chars=12_000,
            seed=17,
            created_at=NOW,
        )

    module.enforce_paid_trial_cap(trial_count=4, max_paid_trials=4)
    with pytest.raises(ValueError, match="paid trial cap"):
        module.enforce_paid_trial_cap(trial_count=4, max_paid_trials=3)


def test_micro_runner_requires_explicit_paid_call_selection() -> None:
    module = _load_script()
    variant = ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH.value

    with pytest.raises(SystemExit):
        module._parse_args(
            [
                "--case",
                "B01",
                "--variant",
                variant,
                "--max-paid-trials",
                "1",
            ]
        )

    args = module._parse_args(
        [
            "--case",
            "B01",
            "--variant",
            variant,
            "--max-paid-trials",
            "1",
            "--execute",
        ]
    )
    assert args.case_ids == ["B01"]
    assert args.variants == [variant]
    assert args.max_paid_trials == 1
    assert args.execute is True


def test_extract_model_response_normalizes_text_and_usage() -> None:
    module = _load_script()
    message = SimpleNamespace(
        content=[{"type": "text", "text": "品牌"}, {"type": "text", "text": "孵化"}],
        usage_metadata={"input_tokens": 120, "output_tokens": 80, "total_tokens": 200},
    )

    output, usage = module.extract_model_response(message)

    assert output == "品牌孵化"
    assert usage == {"input_tokens": 120, "output_tokens": 80, "total_tokens": 200}


def test_micro_runner_uses_configured_model_without_a_second_agent_runtime() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "create_chat_model" in source
    assert "DeerFlowClient" not in source
    assert "create_react_agent" not in source
    assert "LangGraph" not in source
