from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mcn_incubation.context import ArchitectureVariant
from mcn_incubation.domain import DecisionBasis, IncubationDecisionVersion
from mcn_incubation.evaluation import (
    BakeoffStatus,
    CandidateResponse,
    ExpertCalibration,
    TrialEvaluation,
    build_trial_matrix,
    evaluate_response,
    load_eval_cases,
    summarize_bakeoff,
)

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[3]
CASE_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "incubation-eval-cases.jsonl"


def _decision(**overrides) -> IncubationDecisionVersion:
    values = {
        "decision_version_id": "decision-v1",
        "decision_id": "decision-a",
        "version": 1,
        "owner_id": "eval-owner",
        "project_id": "eval-project",
        "created_at": NOW,
        "subject": "有十年会计经验、不能展示孩子的宝妈",
        "expression_carrier": "本人出镜的桌面案例拆解",
        "intended_public": "刚开始经营小生意但不懂基础财务的人",
        "audience_problem": "看不懂利润和现金流的差别",
        "value_promise": "用真实经营小账本讲清一个财务问题",
        "trust_evidence": ("truth-career",),
        "format_plan": "桌面账本加本人旁白",
        "content_engine": "每期拆一个小生意财务误区",
        "monetization_path": "低价财务体检，再承接月度顾问",
        "conversion_path": "内容问题清单 -> 私信领取模板 -> 诊断 -> 顾问服务",
        "first_experiment_id": "experiment-a",
        "basis": DecisionBasis(
            truth_ids=("truth-career", "truth-privacy"),
            rationale=("职业证据可以支撑财务解释",),
            unknowns=("尚不知道本人镜头表现",),
            alternatives=("只录手部和账本",),
            confidence=0.55,
        ),
    }
    values.update(overrides)
    return IncubationDecisionVersion(**values)


def test_eval_corpus_has_36_diverse_business_cases_and_mutations() -> None:
    cases = load_eval_cases(CASE_PATH)

    assert len(cases) == 36
    assert {
        "mother",
        "professional",
        "career",
        "local_business",
        "consumer_brand",
        "single_product",
        "service_product",
        "cold_start",
    }.issubset({case.segment for case in cases})
    assert all(case.mutation for case in cases)
    assert all(case.required_capabilities for case in cases)
    assert any("不能" in constraint and "孩子" in constraint for case in cases for constraint in case.constraints)
    assert any(case.subject_kind.value == "brand" for case in cases)
    assert any(case.subject_kind.value == "product" for case in cases)


def test_bakeoff_matrix_is_complete_fair_and_reproducibly_randomized() -> None:
    cases = load_eval_cases(CASE_PATH)
    first = build_trial_matrix(
        cases,
        model_id="pinned-model-2026-08",
        context_budget_chars=12_000,
        seed=42,
    )
    second = build_trial_matrix(
        cases,
        model_id="pinned-model-2026-08",
        context_budget_chars=12_000,
        seed=42,
    )

    assert first == second
    assert len(first) == 36 * len(ArchitectureVariant)
    assert {trial.model_id for trial in first} == {"pinned-model-2026-08"}
    assert {trial.context_budget_chars for trial in first} == {12_000}
    assert len({trial.trial_id for trial in first}) == len(first)
    assert [trial.variant for trial in first[:5]] != list(ArchitectureVariant)


def test_deterministic_eval_checks_business_output_not_tool_trajectory() -> None:
    case = load_eval_cases(CASE_PATH)[0]
    response = CandidateResponse(
        narrative="先用她真实的会计职业证据，而不是套一个泛宝妈人设。",
        decision=_decision(),
    )

    assessment = evaluate_response(case, response)

    assert assessment.passed
    assert assessment.violations == ()
    assert "tool" not in assessment.criteria
    assert "trajectory" not in assessment.criteria
    assert assessment.criteria["monetization_and_conversion"]
    assert assessment.criteria["expression_and_content_engine"]


def test_eval_rejects_guarantees_stereotypes_and_unsupported_truth_refs() -> None:
    case = load_eval_cases(CASE_PATH)[0]
    response = CandidateResponse(
        narrative="宝妈天然适合育儿赛道，这个形式保证爆款。",
        decision=_decision(
            basis=DecisionBasis(
                truth_ids=("invented-revenue",),
                unknowns=(),
                alternatives=(),
                confidence=0.99,
            )
        ),
    )

    assessment = evaluate_response(case, response)

    assert not assessment.passed
    assert "viral_guarantee" in assessment.violations
    assert "stereotype" in assessment.violations
    assert "unsupported_truth_reference" in assessment.violations


def test_no_architecture_winner_is_declared_before_real_outputs_and_human_calibration() -> None:
    cases = load_eval_cases(CASE_PATH)
    trials = build_trial_matrix(
        cases,
        model_id="pinned-model-2026-08",
        context_budget_chars=12_000,
        seed=42,
    )

    summary = summarize_bakeoff(trials=trials, evaluations=(), expert_calibrations=())

    assert summary.status is BakeoffStatus.DESIGNED
    assert summary.winner is None
    assert summary.completed_trials == 0


def test_bakeoff_requires_expert_calibration_for_every_variant_and_agreement() -> None:
    cases = load_eval_cases(CASE_PATH)
    trials = build_trial_matrix(
        cases,
        model_id="pinned-model-2026-08",
        context_budget_chars=12_000,
        seed=42,
    )
    variant_score = {variant: index / 10 for index, variant in enumerate(ArchitectureVariant)}
    evaluations = tuple(TrialEvaluation(trial_id=trial.trial_id, score=variant_score[trial.variant]) for trial in trials)
    calibration_trials = {variant: next(trial for trial in trials if trial.variant is variant) for variant in ArchitectureVariant}

    partial = summarize_bakeoff(
        trials=trials,
        evaluations=evaluations,
        expert_calibrations=(
            ExpertCalibration(
                trial_id=calibration_trials[ArchitectureVariant.V4_FIXED_WORKFLOW].trial_id,
                score=variant_score[ArchitectureVariant.V4_FIXED_WORKFLOW],
            ),
        ),
    )
    disagreeing = summarize_bakeoff(
        trials=trials,
        evaluations=evaluations,
        expert_calibrations=tuple(
            ExpertCalibration(
                trial_id=trial.trial_id,
                score=variant_score[variant] + (0.5 if index == 0 else 0),
            )
            for index, (variant, trial) in enumerate(calibration_trials.items())
        ),
    )
    calibrated = summarize_bakeoff(
        trials=trials,
        evaluations=evaluations,
        expert_calibrations=tuple(ExpertCalibration(trial_id=trial.trial_id, score=variant_score[variant]) for variant, trial in calibration_trials.items()),
    )

    assert partial.status is BakeoffStatus.NEEDS_ADJUDICATION
    assert partial.winner is None
    assert disagreeing.status is BakeoffStatus.NEEDS_ADJUDICATION
    assert disagreeing.winner is None
    assert calibrated.status is BakeoffStatus.COMPLETE
    assert calibrated.winner is ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH_CASES
