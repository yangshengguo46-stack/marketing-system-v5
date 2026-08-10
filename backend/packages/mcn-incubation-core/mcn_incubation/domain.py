"""Business records for incubation decisions, experiments, and learning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from math import isfinite
from re import fullmatch
from types import MappingProxyType


def _require_id(value: str, *, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")


def _optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} cannot be blank when supplied")
    return normalized


def _text_tuple(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    canonical = tuple(dict.fromkeys(values))
    for value in canonical:
        _require_id(value, field_name=field_name)
    return canonical


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _validate_confidence(value: float | None) -> None:
    if value is not None and (not isfinite(value) or not 0.0 <= value <= 1.0):
        raise ValueError("confidence must be between 0 and 1")


def _numeric_mapping(values: Mapping[str, int | float]) -> MappingProxyType[str, int | float]:
    normalized = dict(values)
    for name, value in normalized.items():
        _require_id(name, field_name="metric name")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("metric values must be numeric")
        if not isfinite(float(value)):
            raise ValueError("metric values must be finite")
    return MappingProxyType(normalized)


class SubjectKind(StrEnum):
    PERSON = "person"
    BRAND = "brand"
    PRODUCT = "product"
    ORGANIZATION = "organization"


class TruthKind(StrEnum):
    USER_FACT = "user_fact"
    SOURCE_FACT = "source_fact"
    INFERENCE = "inference"
    CREATIVE_HYPOTHESIS = "creative_hypothesis"
    UNKNOWN = "unknown"
    APPROVED_DECISION = "approved_decision"
    OBSERVED_OUTCOME = "observed_outcome"


class EvidenceKind(StrEnum):
    USER_ARTIFACT = "user_artifact"
    OFFICIAL_PLATFORM_SNAPSHOT = "official_platform_snapshot"
    PUBLIC_PROFILE = "public_profile"
    PUBLIC_CONTENT = "public_content"
    MARKET_RESEARCH = "market_research"
    FIRST_PARTY_ANALYTICS = "first_party_analytics"
    BUSINESS_RECORD = "business_record"


class EvidenceStatus(StrEnum):
    ACTIVE = "active"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class LearningAction(StrEnum):
    RETAIN = "retain"
    REVISE = "revise"
    STOP = "stop"
    SCALE = "scale"


class CaseStatus(StrEnum):
    ACTIVE = "active"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class IncubationProject:
    project_id: str
    owner_id: str
    working_title: str
    subject_kind: SubjectKind | None
    created_at: datetime

    def __post_init__(self) -> None:
        _require_id(self.project_id, field_name="project_id")
        _require_id(self.owner_id, field_name="owner_id")
        _require_id(self.working_title, field_name="working_title")
        _require_aware(self.created_at, field_name="created_at")


@dataclass(frozen=True, slots=True)
class ProjectTruth:
    truth_id: str
    owner_id: str
    project_id: str
    kind: TruthKind
    statement: str
    created_at: datetime
    source_ref: str | None = None
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    supersedes_truth_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("truth_id", "owner_id", "project_id", "statement"):
            _require_id(getattr(self, name), field_name=name)
        _require_aware(self.created_at, field_name="created_at")
        object.__setattr__(self, "source_ref", _optional_text(self.source_ref, field_name="source_ref"))
        object.__setattr__(
            self,
            "evidence_refs",
            _text_tuple(self.evidence_refs, field_name="evidence_ref"),
        )
        object.__setattr__(
            self,
            "supersedes_truth_id",
            _optional_text(self.supersedes_truth_id, field_name="supersedes_truth_id"),
        )


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    evidence_id: str
    owner_id: str
    project_id: str
    kind: EvidenceKind
    status: EvidenceStatus
    source_locator: str
    captured_at: datetime
    content_hash: str
    observed_facts: tuple[str, ...]
    limitations: tuple[str, ...]
    artifact_refs: tuple[str, ...] = field(default_factory=tuple)
    applicable_platforms: tuple[str, ...] = field(default_factory=tuple)
    applicable_regions: tuple[str, ...] = field(default_factory=tuple)
    source_updated_label: str | None = None
    expires_at: datetime | None = None
    supersedes_evidence_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("evidence_id", "owner_id", "project_id"):
            _require_id(getattr(self, name), field_name=name)
        source_locator = " ".join(self.source_locator.split())
        _require_id(source_locator, field_name="source_locator")
        object.__setattr__(self, "source_locator", source_locator)
        _require_aware(self.captured_at, field_name="captured_at")

        content_hash = self.content_hash.strip().lower()
        if fullmatch(r"[0-9a-f]{64}", content_hash) is None:
            raise ValueError("content_hash must be a SHA-256 hex digest")
        object.__setattr__(self, "content_hash", content_hash)

        for name in (
            "observed_facts",
            "limitations",
            "artifact_refs",
            "applicable_platforms",
            "applicable_regions",
        ):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), field_name=name))
        if not self.observed_facts:
            raise ValueError("evidence requires at least one observed fact")
        if not self.limitations:
            raise ValueError("evidence requires at least one limitation")

        object.__setattr__(
            self,
            "source_updated_label",
            _optional_text(self.source_updated_label, field_name="source_updated_label"),
        )
        if self.expires_at is not None:
            _require_aware(self.expires_at, field_name="expires_at")
            if self.expires_at <= self.captured_at:
                raise ValueError("expires_at must be later than captured_at")
        object.__setattr__(
            self,
            "supersedes_evidence_id",
            _optional_text(
                self.supersedes_evidence_id,
                field_name="supersedes_evidence_id",
            ),
        )
        if self.supersedes_evidence_id == self.evidence_id:
            raise ValueError("evidence cannot supersede itself")

    def is_refresh_due(self, *, as_of: datetime) -> bool:
        _require_aware(as_of, field_name="as_of")
        return self.expires_at is not None and as_of >= self.expires_at


@dataclass(frozen=True, slots=True)
class DecisionBasis:
    truth_ids: tuple[str, ...] = field(default_factory=tuple)
    rationale: tuple[str, ...] = field(default_factory=tuple)
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    alternatives: tuple[str, ...] = field(default_factory=tuple)
    confidence: float | None = None

    def __post_init__(self) -> None:
        for name in ("truth_ids", "rationale", "unknowns", "alternatives"):
            object.__setattr__(
                self,
                name,
                _text_tuple(getattr(self, name), field_name=name),
            )
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class IncubationBrief:
    brief_version_id: str
    brief_id: str
    version: int
    owner_id: str
    project_id: str
    created_at: datetime
    subject_kind: SubjectKind | None = None
    subject_summary: str | None = None
    available_assets: tuple[str, ...] = field(default_factory=tuple)
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    offers: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    goals: tuple[str, ...] = field(default_factory=tuple)
    truth_ids: tuple[str, ...] = field(default_factory=tuple)
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    supersedes_brief_version_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("brief_version_id", "brief_id", "owner_id", "project_id"):
            _require_id(getattr(self, name), field_name=name)
        if self.version < 1:
            raise ValueError("brief version must be positive")
        _require_aware(self.created_at, field_name="created_at")
        object.__setattr__(
            self,
            "subject_summary",
            _optional_text(self.subject_summary, field_name="subject_summary"),
        )
        for name in (
            "available_assets",
            "capabilities",
            "offers",
            "constraints",
            "goals",
            "truth_ids",
            "unknowns",
        ):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), field_name=name))
        object.__setattr__(
            self,
            "supersedes_brief_version_id",
            _optional_text(
                self.supersedes_brief_version_id,
                field_name="supersedes_brief_version_id",
            ),
        )

    @property
    def missing_fields(self) -> tuple[str, ...]:
        values = {
            "subject_kind": self.subject_kind,
            "subject_summary": self.subject_summary,
            "available_assets": self.available_assets,
            "capabilities": self.capabilities,
            "offers": self.offers,
            "goals": self.goals,
        }
        return tuple(name for name, value in values.items() if not value)


@dataclass(frozen=True, slots=True)
class IncubationDecisionVersion:
    decision_version_id: str
    decision_id: str
    version: int
    owner_id: str
    project_id: str
    created_at: datetime
    basis: DecisionBasis
    subject: str | None = None
    expression_carrier: str | None = None
    intended_public: str | None = None
    audience_problem: str | None = None
    value_promise: str | None = None
    trust_evidence: tuple[str, ...] = field(default_factory=tuple)
    format_plan: str | None = None
    content_engine: str | None = None
    monetization_path: str | None = None
    conversion_path: str | None = None
    first_experiment_id: str | None = None
    supersedes_decision_version_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("decision_version_id", "decision_id", "owner_id", "project_id"):
            _require_id(getattr(self, name), field_name=name)
        if self.version < 1:
            raise ValueError("decision version must be positive")
        _require_aware(self.created_at, field_name="created_at")
        for name in (
            "subject",
            "expression_carrier",
            "intended_public",
            "audience_problem",
            "value_promise",
            "format_plan",
            "content_engine",
            "monetization_path",
            "conversion_path",
            "first_experiment_id",
            "supersedes_decision_version_id",
        ):
            object.__setattr__(self, name, _optional_text(getattr(self, name), field_name=name))
        object.__setattr__(
            self,
            "trust_evidence",
            _text_tuple(self.trust_evidence, field_name="trust_evidence"),
        )

    @property
    def missing_fields(self) -> tuple[str, ...]:
        values = {
            "subject": self.subject,
            "expression_carrier": self.expression_carrier,
            "intended_public": self.intended_public,
            "audience_problem": self.audience_problem,
            "value_promise": self.value_promise,
            "trust_evidence": self.trust_evidence,
            "format_plan": self.format_plan,
            "content_engine": self.content_engine,
            "monetization_path": self.monetization_path,
            "conversion_path": self.conversion_path,
            "first_experiment_id": self.first_experiment_id,
        }
        return tuple(name for name, value in values.items() if not value)


@dataclass(frozen=True, slots=True)
class IncubationExperiment:
    experiment_id: str
    owner_id: str
    project_id: str
    decision_version_id: str
    created_at: datetime
    hypothesis: str | None = None
    content_variable: str | None = None
    platform: str | None = None
    format_name: str | None = None
    cost_cap: float | None = None
    currency: str | None = None
    observation_window: str | None = None
    success_signals: tuple[str, ...] = field(default_factory=tuple)
    failure_signals: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("experiment_id", "owner_id", "project_id", "decision_version_id"):
            _require_id(getattr(self, name), field_name=name)
        _require_aware(self.created_at, field_name="created_at")
        for name in (
            "hypothesis",
            "content_variable",
            "platform",
            "format_name",
            "currency",
            "observation_window",
        ):
            object.__setattr__(self, name, _optional_text(getattr(self, name), field_name=name))
        if self.cost_cap is not None and (not isfinite(self.cost_cap) or self.cost_cap < 0):
            raise ValueError("cost_cap must be finite and non-negative")
        for name in ("success_signals", "failure_signals"):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), field_name=name))

    @property
    def missing_fields(self) -> tuple[str, ...]:
        values = {
            "hypothesis": self.hypothesis,
            "content_variable": self.content_variable,
            "observation_window": self.observation_window,
            "success_signals": self.success_signals,
        }
        return tuple(name for name, value in values.items() if not value)


@dataclass(frozen=True, slots=True)
class OutcomeObservation:
    observation_id: str
    owner_id: str
    project_id: str
    experiment_id: str
    observed_at: datetime
    observed_facts: tuple[str, ...] = field(default_factory=tuple)
    metrics: Mapping[str, int | float] = field(default_factory=dict)
    audience_signals: tuple[str, ...] = field(default_factory=tuple)
    commercial_signals: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("observation_id", "owner_id", "project_id", "experiment_id"):
            _require_id(getattr(self, name), field_name=name)
        _require_aware(self.observed_at, field_name="observed_at")
        for name in (
            "observed_facts",
            "audience_signals",
            "commercial_signals",
            "limitations",
            "evidence_refs",
        ):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), field_name=name))
        object.__setattr__(self, "metrics", _numeric_mapping(self.metrics))

    @property
    def missing_fields(self) -> tuple[str, ...]:
        values = {
            "observed_facts": self.observed_facts,
            "metrics_or_signals": (
                *self.metrics.keys(),
                *self.audience_signals,
                *self.commercial_signals,
            ),
        }
        return tuple(name for name, value in values.items() if not value)


@dataclass(frozen=True, slots=True)
class LearningDecision:
    learning_decision_id: str
    owner_id: str
    project_id: str
    experiment_id: str
    action: LearningAction | None
    observation_ids: tuple[str, ...]
    rationale: tuple[str, ...]
    created_at: datetime
    next_experiment: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "learning_decision_id",
            "owner_id",
            "project_id",
            "experiment_id",
        ):
            _require_id(getattr(self, name), field_name=name)
        _require_aware(self.created_at, field_name="created_at")
        for name in ("observation_ids", "rationale"):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), field_name=name))
        object.__setattr__(
            self,
            "next_experiment",
            _optional_text(self.next_experiment, field_name="next_experiment"),
        )

    @property
    def missing_fields(self) -> tuple[str, ...]:
        values = {
            "action": self.action,
            "observation_ids": self.observation_ids,
            "rationale": self.rationale,
        }
        return tuple(name for name, value in values.items() if not value)


@dataclass(frozen=True, slots=True)
class MethodCard:
    method_card_id: str
    version: int
    capability: str
    title: str
    applies_when: tuple[str, ...]
    lens: tuple[str, ...]
    evidence_needs: tuple[str, ...]
    counterexamples: tuple[str, ...]
    source_refs: tuple[str, ...]
    search_terms: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("method_card_id", "capability", "title"):
            _require_id(getattr(self, name), field_name=name)
        if self.version < 1:
            raise ValueError("method card version must be positive")
        for name in (
            "applies_when",
            "lens",
            "evidence_needs",
            "counterexamples",
            "source_refs",
            "search_terms",
        ):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), field_name=name))
        if not self.source_refs:
            raise ValueError("method card requires at least one source reference")


@dataclass(frozen=True, slots=True)
class CaseEpisode:
    case_episode_id: str
    owner_id: str
    project_id: str
    subject_kind: SubjectKind
    status: CaseStatus
    decision_version_id: str
    outcome_observation_ids: tuple[str, ...]
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    experiment_ids: tuple[str, ...] = field(default_factory=tuple)
    learning_decision_ids: tuple[str, ...] = field(default_factory=tuple)
    conditions: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    platforms: tuple[str, ...] = field(default_factory=tuple)
    supports_claims: tuple[str, ...] = field(default_factory=tuple)
    contradicts_claims: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    supersedes_case_episode_id: str | None = None
    cross_project_eligible: bool = False

    def __post_init__(self) -> None:
        for name in (
            "case_episode_id",
            "owner_id",
            "project_id",
            "decision_version_id",
        ):
            _require_id(getattr(self, name), field_name=name)
        _require_aware(self.created_at, field_name="created_at")
        if not self.outcome_observation_ids:
            raise ValueError("case memory requires at least one observed outcome")
        if self.reviewed_by is None or self.reviewed_at is None:
            raise ValueError("case memory requires human review")
        _require_id(self.reviewed_by, field_name="reviewed_by")
        _require_aware(self.reviewed_at, field_name="reviewed_at")
        for name in (
            "outcome_observation_ids",
            "experiment_ids",
            "learning_decision_ids",
            "conditions",
            "tags",
            "platforms",
            "supports_claims",
            "contradicts_claims",
            "limitations",
        ):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), field_name=name))
        object.__setattr__(
            self,
            "supersedes_case_episode_id",
            _optional_text(
                self.supersedes_case_episode_id,
                field_name="supersedes_case_episode_id",
            ),
        )


@dataclass(frozen=True, slots=True)
class CaseRecall:
    supporting: tuple[CaseEpisode, ...]
    counterexamples: tuple[CaseEpisode, ...]


__all__ = [
    "CaseEpisode",
    "CaseRecall",
    "CaseStatus",
    "DecisionBasis",
    "EvidenceItem",
    "EvidenceKind",
    "EvidenceStatus",
    "IncubationBrief",
    "IncubationDecisionVersion",
    "IncubationExperiment",
    "IncubationProject",
    "LearningAction",
    "LearningDecision",
    "MethodCard",
    "OutcomeObservation",
    "ProjectTruth",
    "SubjectKind",
    "TruthKind",
]
