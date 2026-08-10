"""Outcome-focused evaluation protocol for the incubation architecture bakeoff."""

from __future__ import annotations

import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

from mcn_incubation.context import ArchitectureVariant
from mcn_incubation.domain import IncubationDecisionVersion, SubjectKind


@dataclass(frozen=True, slots=True)
class EvalCase:
    case_id: str
    segment: str
    subject_kind: SubjectKind
    scenario: str
    facts: tuple[str, ...]
    truth_ids: tuple[str, ...]
    constraints: tuple[str, ...]
    goals: tuple[str, ...]
    offers: tuple[str, ...]
    mutation: str
    required_capabilities: tuple[str, ...]


def _strings(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a string list")
    return tuple(value)


def load_eval_cases(path: Path) -> tuple[EvalCase, ...]:
    """Load the versioned JSONL corpus and reject duplicate identities."""

    cases: list[EvalCase] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        raw = json.loads(raw_line)
        if not isinstance(raw, dict):
            raise ValueError(f"eval line {line_number} must be an object")
        cases.append(
            EvalCase(
                case_id=str(raw["case_id"]),
                segment=str(raw["segment"]),
                subject_kind=SubjectKind(str(raw["subject_kind"])),
                scenario=str(raw["scenario"]),
                facts=_strings(raw["facts"], field_name="facts"),
                truth_ids=_strings(raw["truth_ids"], field_name="truth_ids"),
                constraints=_strings(raw["constraints"], field_name="constraints"),
                goals=_strings(raw["goals"], field_name="goals"),
                offers=_strings(raw["offers"], field_name="offers"),
                mutation=str(raw["mutation"]),
                required_capabilities=_strings(
                    raw["required_capabilities"],
                    field_name="required_capabilities",
                ),
            )
        )
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("eval case ids must be unique")
    return tuple(cases)


@dataclass(frozen=True, slots=True)
class CandidateResponse:
    narrative: str
    decision: IncubationDecisionVersion


@dataclass(frozen=True, slots=True)
class DeterministicAssessment:
    passed: bool
    score: float
    criteria: Mapping[str, bool]
    violations: tuple[str, ...]


_GUARANTEES = ("保证爆款", "必爆", "一定会火", "保证涨粉", "保证成交")
_STEREOTYPES = ("宝妈天然", "女性天然", "老人都", "年轻人都", "男人天然")


def evaluate_response(
    case: EvalCase,
    response: CandidateResponse,
) -> DeterministicAssessment:
    """Check observable answer properties without inspecting internal tool use."""

    decision = response.decision
    criteria = {
        "subject_and_audience": bool(decision.subject and decision.intended_public and decision.audience_problem),
        "expression_and_content_engine": bool(decision.expression_carrier and decision.format_plan and decision.content_engine),
        "monetization_and_conversion": bool(decision.monetization_path and decision.conversion_path),
        "first_experiment": bool(decision.first_experiment_id),
        "uncertainty_and_alternative": bool(decision.basis.unknowns and decision.basis.alternatives),
        "grounded_basis": set((*decision.basis.truth_ids, *decision.trust_evidence)).issubset(case.truth_ids),
    }
    violations: list[str] = []
    if any(phrase in response.narrative for phrase in _GUARANTEES):
        violations.append("viral_guarantee")
    if any(phrase in response.narrative for phrase in _STEREOTYPES):
        violations.append("stereotype")
    if not criteria["grounded_basis"]:
        violations.append("unsupported_truth_reference")
    if decision.basis.confidence is not None and decision.basis.confidence > 0.8 and not decision.basis.unknowns:
        violations.append("unqualified_overconfidence")
    score = sum(criteria.values()) / len(criteria)
    return DeterministicAssessment(
        passed=all(criteria.values()) and not violations,
        score=score,
        criteria=MappingProxyType(criteria),
        violations=tuple(violations),
    )


@dataclass(frozen=True, slots=True)
class BakeoffTrial:
    trial_id: str
    case_id: str
    variant: ArchitectureVariant
    model_id: str
    context_budget_chars: int


def build_trial_matrix(
    cases: Sequence[EvalCase],
    *,
    model_id: str,
    context_budget_chars: int,
    seed: int,
) -> tuple[BakeoffTrial, ...]:
    if not model_id.strip():
        raise ValueError("model_id cannot be blank")
    if context_budget_chars < 1:
        raise ValueError("context_budget_chars must be positive")
    trials = [
        BakeoffTrial(
            trial_id=f"{case.case_id}:{variant.value}",
            case_id=case.case_id,
            variant=variant,
            model_id=model_id,
            context_budget_chars=context_budget_chars,
        )
        for case in cases
        for variant in ArchitectureVariant
    ]
    random.Random(seed).shuffle(trials)
    return tuple(trials)


class BakeoffStatus(StrEnum):
    DESIGNED = "designed"
    RUNNING = "running"
    NEEDS_ADJUDICATION = "needs_adjudication"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class TrialEvaluation:
    trial_id: str
    score: float


@dataclass(frozen=True, slots=True)
class ExpertCalibration:
    trial_id: str
    score: float


@dataclass(frozen=True, slots=True)
class BakeoffSummary:
    status: BakeoffStatus
    winner: ArchitectureVariant | None
    completed_trials: int
    total_trials: int


DEFAULT_MAX_CALIBRATION_ERROR = 0.2


def _index_scores(
    scores: Sequence[TrialEvaluation] | Sequence[ExpertCalibration],
    *,
    valid_trial_ids: set[str],
    label: str,
) -> dict[str, float]:
    indexed: dict[str, float] = {}
    for score in scores:
        if score.trial_id not in valid_trial_ids:
            raise ValueError(f"{label} references unknown trial: {score.trial_id}")
        if score.trial_id in indexed:
            raise ValueError(f"{label} contains duplicate trial: {score.trial_id}")
        if not 0 <= score.score <= 1:
            raise ValueError(f"{label} score must be between 0 and 1")
        indexed[score.trial_id] = score.score
    return indexed


def summarize_bakeoff(
    *,
    trials: Sequence[BakeoffTrial],
    evaluations: Sequence[TrialEvaluation],
    expert_calibrations: Sequence[ExpertCalibration],
    max_calibration_error: float = DEFAULT_MAX_CALIBRATION_ERROR,
) -> BakeoffSummary:
    if not 0 <= max_calibration_error <= 1:
        raise ValueError("max_calibration_error must be between 0 and 1")
    variant_by_trial = {trial.trial_id: trial.variant for trial in trials}
    if len(variant_by_trial) != len(trials):
        raise ValueError("trial ids must be unique")
    valid_trial_ids = set(variant_by_trial)
    evaluation_by_trial = _index_scores(
        evaluations,
        valid_trial_ids=valid_trial_ids,
        label="evaluation",
    )
    calibration_by_trial = _index_scores(
        expert_calibrations,
        valid_trial_ids=valid_trial_ids,
        label="expert calibration",
    )
    completed = len(evaluation_by_trial)
    if completed == 0:
        return BakeoffSummary(
            status=BakeoffStatus.DESIGNED,
            winner=None,
            completed_trials=0,
            total_trials=len(trials),
        )
    if completed < len(trials):
        return BakeoffSummary(
            status=BakeoffStatus.RUNNING,
            winner=None,
            completed_trials=completed,
            total_trials=len(trials),
        )
    calibrated_variants = {variant_by_trial[trial_id] for trial_id in calibration_by_trial}
    expected_variants = set(variant_by_trial.values())
    calibration_agrees = all(abs(evaluation_by_trial[trial_id] - expert_score) <= max_calibration_error for trial_id, expert_score in calibration_by_trial.items())
    if calibrated_variants != expected_variants or not calibration_agrees:
        return BakeoffSummary(
            status=BakeoffStatus.NEEDS_ADJUDICATION,
            winner=None,
            completed_trials=completed,
            total_trials=len(trials),
        )

    totals: dict[ArchitectureVariant, list[float]] = {variant: [] for variant in ArchitectureVariant}
    for trial_id, score in evaluation_by_trial.items():
        totals[variant_by_trial[trial_id]].append(score)
    means = {variant: sum(scores) / len(scores) for variant, scores in totals.items() if scores}
    winner = max(means, key=lambda variant: (means[variant], variant.value))
    return BakeoffSummary(
        status=BakeoffStatus.COMPLETE,
        winner=winner,
        completed_trials=completed,
        total_trials=len(trials),
    )


__all__ = [
    "BakeoffStatus",
    "CandidateResponse",
    "DEFAULT_MAX_CALIBRATION_ERROR",
    "EvalCase",
    "ExpertCalibration",
    "TrialEvaluation",
    "build_trial_matrix",
    "evaluate_response",
    "load_eval_cases",
    "summarize_bakeoff",
]
