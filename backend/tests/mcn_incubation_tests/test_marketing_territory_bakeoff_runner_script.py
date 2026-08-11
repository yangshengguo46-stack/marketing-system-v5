from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mcn_incubation.territory_evaluation import (
    CONTENT_WORLD_EXPLORATION_CONTEXT,
    CONTENT_WORLD_EXPLORATION_OPERATOR_CARD,
    CONTENT_WORLD_OPERATOR_CARD,
    TERRITORY_METHOD_V2_CARD,
    ResponseMode,
    TerritoryEvalVariant,
    load_territory_anchor_cases,
    load_territory_contrast_cases,
    render_territory_explorer_context,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "run_marketing_territory_bakeoff.py"
CASE_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "marketing-territory-contrast-cases.jsonl"
ANCHOR_CASE_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "marketing-territory-eval-cases.jsonl"
CONTENT_WORLD_CASE_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "content-world-exploration-eval-cases.jsonl"
NOW = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)


def _load_script():
    spec = importlib.util.spec_from_file_location("run_marketing_territory_bakeoff", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_contrast_corpus_has_three_complete_same_label_pairs() -> None:
    cases = load_territory_contrast_cases(CASE_PATH)
    groups: dict[str, list[object]] = {}
    for case in cases:
        groups.setdefault(case.contrast_group, []).append(case)

    assert len(cases) == 6
    assert {name: len(items) for name, items in groups.items()} == {
        "fruit-business": 2,
        "fruit-grower": 2,
        "mother-role": 2,
    }
    assert all(case.review_status == "needs_expert_review" for case in cases)


def test_expert_anchor_loader_keeps_the_answer_out_of_model_context() -> None:
    module = _load_script()
    anchor = next(case for case in load_territory_anchor_cases(ANCHOR_CASE_PATH) if case.case_id == "MT01-gold-gift")
    trials = module.prepare_anchor_trials(
        cases=(anchor,),
        variants=(
            TerritoryEvalVariant.BASELINE,
            TerritoryEvalVariant.TERRITORY_METHOD_V2,
        ),
        context_budget_chars=8_000,
        seed=29,
        include_mutation=False,
        response_mode=ResponseMode.NATURAL_JUDGMENT,
    )

    assert anchor.review_status == "expert_anchor"
    assert anchor.expert_anchor["head_category"] == "礼品"
    assert len(trials) == 2
    assert trials[0].user_message == trials[1].user_message
    for trial in trials:
        assert anchor.request in trial.user_message
        assert anchor.mutation not in trial.user_message
        assert "observable_success" not in trial.user_message
        assert "礼物如何参与人情、关系、礼仪" not in trial.user_message
        assert all(failure not in trial.user_message for failure in anchor.observable_failures)


def test_conversation_operator_candidate_is_answer_blind_and_contains_no_charlie_material() -> None:
    module = _load_script()
    cases = load_territory_anchor_cases(CONTENT_WORLD_CASE_PATH)
    trials = module.prepare_anchor_trials(
        cases=cases,
        variants=(
            TerritoryEvalVariant.BASELINE,
            TerritoryEvalVariant.CONTENT_WORLD_OPERATORS,
        ),
        context_budget_chars=8_000,
        seed=43,
        include_mutation=False,
        response_mode=ResponseMode.NATURAL_JUDGMENT,
    )

    assert {case.case_id for case in cases} == {
        "CW01-gold-gift",
        "CW02-fruit-world",
    }
    assert all(case.review_status == "expert_correction" for case in cases)
    assert len(trials) == 4
    for case in cases:
        by_variant = {trial.variant: trial for trial in trials if trial.case.case_id == case.case_id}
        baseline = by_variant[TerritoryEvalVariant.BASELINE]
        operators = by_variant[TerritoryEvalVariant.CONTENT_WORLD_OPERATORS]
        assert baseline.user_message == operators.user_message
        assert "<content_world_operators>" not in baseline.system_context
        assert "<content_world_operators>" in operators.system_context
        assert all(expectation not in operators.user_message for expectation in case.observable_success)
        assert all(failure not in operators.user_message for failure in case.observable_failures)
        assert str(case.expert_anchor) not in operators.user_message

    for marker in (
        "向上抽象",
        "向下拆分",
        "横向展开",
        "跨维连接",
        "时间 × 空间 × 事件 × 人物 × 冲突",
        "不是固定流程",
    ):
        assert marker in CONTENT_WORLD_OPERATOR_CARD
    for leaked_answer in ("查理", "黄金", "礼品", "水果", "榴莲"):
        assert leaked_answer not in CONTENT_WORLD_OPERATOR_CARD


def test_exploration_only_mode_removes_final_strategy_pressure_and_isolates_the_operator_card() -> None:
    module = _load_script()
    cases = load_territory_anchor_cases(CONTENT_WORLD_CASE_PATH)
    trials = module.prepare_anchor_trials(
        cases=cases,
        variants=(
            TerritoryEvalVariant.BASELINE,
            TerritoryEvalVariant.CONTENT_WORLD_OPERATORS,
        ),
        context_budget_chars=8_000,
        seed=47,
        include_mutation=False,
        response_mode=ResponseMode.CONTENT_WORLD_EXPLORATION,
    )

    assert len(trials) == 4
    assert "只读" in CONTENT_WORLD_EXPLORATION_CONTEXT
    for case in cases:
        by_variant = {trial.variant: trial for trial in trials if trial.case.case_id == case.case_id}
        baseline = by_variant[TerritoryEvalVariant.BASELINE]
        operators = by_variant[TerritoryEvalVariant.CONTENT_WORLD_OPERATORS]

        assert baseline.user_message == operators.user_message
        assert baseline.system_context == CONTENT_WORLD_EXPLORATION_CONTEXT
        assert operators.system_context == (f"{CONTENT_WORLD_EXPLORATION_CONTEXT}\n\n{CONTENT_WORLD_EXPLORATION_OPERATOR_CARD}")
        assert case.request in baseline.user_message
        assert all(fact in baseline.user_message for fact in case.known_facts)
        assert baseline.model_call_count == operators.model_call_count == 1

        combined = f"{baseline.system_context}\n{operators.system_context}\n{baseline.user_message}"
        for final_delivery_pressure in (
            "Incubation is your root responsibility",
            "负责结果的 MCN 孵化负责人",
            "表现形式",
            "变现假设",
            "最小实验",
            "B端",
            "C端",
            "行业号",
        ):
            assert final_delivery_pressure not in combined

    for marker in (
        "向上抽象",
        "向下拆分",
        "横向展开",
        "跨维连接",
        "时间 × 空间 × 事件 × 人物 × 冲突",
    ):
        assert marker in CONTENT_WORLD_EXPLORATION_OPERATOR_CARD
    for leaked_answer in ("查理", "黄金", "礼品", "水果", "榴莲"):
        assert leaked_answer not in CONTENT_WORLD_EXPLORATION_OPERATOR_CARD

    with pytest.raises(ValueError, match="content-world exploration"):
        module.prepare_anchor_trials(
            cases=(cases[0],),
            variants=(TerritoryEvalVariant.TERRITORY_METHOD_V2,),
            context_budget_chars=8_000,
            seed=47,
            include_mutation=False,
            response_mode=ResponseMode.CONTENT_WORLD_EXPLORATION,
        )


def test_source_mechanism_candidate_retrieves_context_without_changing_the_anchor_request() -> None:
    module = _load_script()
    anchor = next(case for case in load_territory_anchor_cases(ANCHOR_CASE_PATH) if case.case_id == "MT01-gold-gift")
    trials = module.prepare_anchor_trials(
        cases=(anchor,),
        variants=(
            TerritoryEvalVariant.BASELINE,
            TerritoryEvalVariant.TERRITORY_METHOD_V2_MECHANISMS,
        ),
        context_budget_chars=8_000,
        seed=31,
        include_mutation=False,
        response_mode=ResponseMode.NATURAL_JUDGMENT,
    )
    by_variant = {trial.variant: trial for trial in trials}
    baseline = by_variant[TerritoryEvalVariant.BASELINE]
    mechanisms = by_variant[TerritoryEvalVariant.TERRITORY_METHOD_V2_MECHANISMS]

    assert baseline.user_message == mechanisms.user_message
    assert "<human_mechanism_context>" not in baseline.system_context
    assert "<human_mechanism_context>" in mechanisms.system_context
    assert "gift-exchange-v1" in mechanisms.system_context
    assert "这些观察不是当前客户事实" in mechanisms.system_context


def test_two_pass_candidate_counts_both_calls_and_keeps_explorer_read_only() -> None:
    module = _load_script()
    anchor = next(case for case in load_territory_anchor_cases(ANCHOR_CASE_PATH) if case.case_id == "MT01-gold-gift")
    trials = module.prepare_anchor_trials(
        cases=(anchor,),
        variants=(
            TerritoryEvalVariant.BASELINE,
            TerritoryEvalVariant.TERRITORY_TWO_PASS_MECHANISMS,
        ),
        context_budget_chars=8_000,
        seed=37,
        include_mutation=False,
        response_mode=ResponseMode.NATURAL_JUDGMENT,
    )
    by_variant = {trial.variant: trial for trial in trials}

    assert by_variant[TerritoryEvalVariant.BASELINE].model_call_count == 1
    two_pass = by_variant[TerritoryEvalVariant.TERRITORY_TWO_PASS_MECHANISMS]
    assert two_pass.model_call_count == 2
    assert two_pass.exploration_message is not None
    assert anchor.request in two_pass.exploration_message
    assert "负责结果的 MCN 孵化负责人" not in two_pass.exploration_message
    assert "表现形式" not in two_pass.exploration_message
    assert "变现" not in two_pass.exploration_message
    assert module.count_paid_calls(trials) == 3
    module.enforce_paid_trial_cap(trial_count=module.count_paid_calls(trials), max_paid_trials=3)

    explorer_context = render_territory_explorer_context(anchor.request)
    assert "只读内容领地探索任务" in explorer_context
    assert "不要替 Lead 做最终选择" in explorer_context
    assert "<human_mechanism_context>" in explorer_context
    assert "价格" in explorer_context


def test_prepare_trials_changes_only_the_method_context_and_hides_rubric_answers() -> None:
    module = _load_script()
    cases = module.select_contrast_groups(
        load_territory_contrast_cases(CASE_PATH),
        ("fruit-business",),
    )
    trials = module.prepare_trials(
        cases=cases,
        variants=(TerritoryEvalVariant.BASELINE, TerritoryEvalVariant.TERRITORY_METHOD),
        context_budget_chars=8_000,
        seed=19,
        include_mutation=False,
    )

    assert len(trials) == 4
    assert len({trial.trial_id for trial in trials}) == 4
    assert all(trial.estimated_chars <= 8_000 for trial in trials)
    for case in cases:
        by_variant = {trial.variant: trial for trial in trials if trial.case.case_id == case.case_id}
        baseline = by_variant[TerritoryEvalVariant.BASELINE]
        method = by_variant[TerritoryEvalVariant.TERRITORY_METHOD]
        assert method.system_context.startswith(baseline.system_context)
        assert "<content_territory_method>" not in baseline.system_context
        assert "<content_territory_method>" in method.system_context
        assert baseline.user_message == method.user_message
        assert case.mutation not in baseline.user_message
        assert all(expectation not in baseline.user_message for expectation in case.must_change)
        assert all(lens not in baseline.user_message for lens in case.subject_lenses)
        assert all(fact in baseline.user_message for fact in case.known_facts)


def test_second_candidate_uses_a_natural_answer_without_industry_leakage_or_fill_in_schema() -> None:
    module = _load_script()
    cases = module.select_contrast_groups(
        load_territory_contrast_cases(CASE_PATH),
        ("mother-role",),
    )
    trials = module.prepare_trials(
        cases=cases,
        variants=(
            TerritoryEvalVariant.BASELINE,
            TerritoryEvalVariant.TERRITORY_METHOD_V2,
        ),
        context_budget_chars=8_000,
        seed=23,
        include_mutation=False,
        response_mode=ResponseMode.NATURAL_JUDGMENT,
    )

    assert all("territory_candidates" not in trial.user_message for trial in trials)
    assert all("只输出一个有效 JSON" not in trial.user_message for trial in trials)
    assert all("不要为了完整而补齐" in trial.user_message for trial in trials)
    for case in cases:
        by_variant = {trial.variant: trial for trial in trials if trial.case.case_id == case.case_id}
        baseline = by_variant[TerritoryEvalVariant.BASELINE]
        method = by_variant[TerritoryEvalVariant.TERRITORY_METHOD_V2]
        assert baseline.user_message == method.user_message
        assert "<content_territory_method_v2>" not in baseline.system_context
        assert "<content_territory_method_v2>" in method.system_context

    assert all(term not in TERRITORY_METHOD_V2_CARD for term in ("黄金", "礼品", "水果", "果农", "宝妈"))


def test_group_selection_rejects_partial_or_duplicate_experiment_inputs() -> None:
    module = _load_script()
    cases = load_territory_contrast_cases(CASE_PATH)

    selected = module.select_contrast_groups(cases, ("mother-role",))
    assert {case.case_id for case in selected} == {
        "TC05-mother-accountant",
        "TC06-mother-household-systems",
    }
    with pytest.raises(ValueError, match="unknown contrast groups"):
        module.select_contrast_groups(cases, ("missing",))
    with pytest.raises(ValueError, match="contrast groups must be unique"):
        module.select_contrast_groups(cases, ("mother-role", "mother-role"))

    anchors = load_territory_anchor_cases(ANCHOR_CASE_PATH)
    assert module.select_anchor_cases(anchors, ("MT01-gold-gift",))[0].case_id == "MT01-gold-gift"
    with pytest.raises(ValueError, match="unknown anchor case ids"):
        module.select_anchor_cases(anchors, ("missing",))


def test_territory_runner_requires_explicit_paid_call_cap_and_acknowledgement() -> None:
    module = _load_script()

    with pytest.raises(SystemExit):
        module._parse_args(
            [
                "--group",
                "fruit-business",
                "--variant",
                "baseline",
                "--max-paid-trials",
                "2",
            ]
        )

    args = module._parse_args(
        [
            "--group",
            "fruit-business",
            "--variant",
            "baseline",
            "--variant",
            "territory_method",
            "--max-paid-trials",
            "4",
            "--execute",
        ]
    )
    assert args.groups == ["fruit-business"]
    assert args.variants == ["baseline", "territory_method"]
    assert args.max_paid_trials == 4
    assert args.execute is True
    assert args.response_mode == "structured_json"

    module.enforce_paid_trial_cap(trial_count=4, max_paid_trials=4)
    with pytest.raises(ValueError, match="paid trial cap"):
        module.enforce_paid_trial_cap(trial_count=4, max_paid_trials=3)

    anchor_args = module._parse_args(
        [
            "--anchor-case",
            "MT01-gold-gift",
            "--variant",
            "baseline",
            "--variant",
            "territory_method_v2",
            "--response-mode",
            "natural_judgment",
            "--max-paid-trials",
            "2",
            "--execute",
        ]
    )
    assert anchor_args.anchor_case_ids == ["MT01-gold-gift"]
    assert anchor_args.groups is None


def test_territory_runner_is_an_isolated_model_eval_not_an_agent_runtime() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "create_chat_model" in source
    assert "default_method_library" not in source
    assert "DeerFlowClient" not in source
    assert "create_react_agent" not in source
    assert "LangGraph" not in source
