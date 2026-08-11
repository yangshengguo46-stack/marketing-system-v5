"""Owner-scoped append-only persistence for incubation truth and learning."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, TypeVar

from sqlalchemy import Table, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mcn_incubation.domain import (
    CaseEpisode,
    CaseStatus,
    DecisionBasis,
    EvidenceItem,
    EvidenceKind,
    EvidenceStatus,
    IncubationBrief,
    IncubationDecisionVersion,
    IncubationExperiment,
    IncubationProject,
    LearningAction,
    LearningDecision,
    OutcomeObservation,
    ProjectTruth,
    SubjectKind,
    TerritoryCandidate,
    TruthKind,
)
from mcn_incubation.persistence_schema import (
    incubation_brief_versions,
    incubation_case_episodes,
    incubation_decision_versions,
    incubation_evidence_items,
    incubation_experiments,
    incubation_learning_decisions,
    incubation_operation_receipts,
    incubation_outcome_observations,
    incubation_project_truths,
    incubation_projects,
)


class OwnershipViolation(ValueError):
    """A record was referenced outside its owner or project boundary."""


class ImmutableRecordConflict(ValueError):
    """An immutable identity already exists with different content."""


class IdempotencyConflict(ValueError):
    """An operation key was reused for a different request."""


_T = TypeVar("_T")
_Record = Mapping[str, Any]


def _dt(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise TypeError(f"expected datetime, got {type(value).__name__}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("expected a JSON string list")
    return tuple(str(item) for item in value)


def _optional(value: object) -> str | None:
    return None if value is None else str(value)


def _project_payload(value: IncubationProject) -> dict[str, Any]:
    return {
        "project_id": value.project_id,
        "owner_id": value.owner_id,
        "working_title": value.working_title,
        "subject_kind": value.subject_kind.value if value.subject_kind else None,
        "created_at": value.created_at.isoformat(),
    }


def _project_from(payload: _Record) -> IncubationProject:
    raw_kind = payload["subject_kind"]
    return IncubationProject(
        project_id=str(payload["project_id"]),
        owner_id=str(payload["owner_id"]),
        working_title=str(payload["working_title"]),
        subject_kind=None if raw_kind is None else SubjectKind(str(raw_kind)),
        created_at=_dt(payload["created_at"]),
    )


def _truth_payload(value: ProjectTruth) -> dict[str, Any]:
    return {
        "truth_id": value.truth_id,
        "owner_id": value.owner_id,
        "project_id": value.project_id,
        "kind": value.kind.value,
        "statement": value.statement,
        "created_at": value.created_at.isoformat(),
        "source_ref": value.source_ref,
        "evidence_refs": list(value.evidence_refs),
        "supersedes_truth_id": value.supersedes_truth_id,
    }


def _truth_from(payload: _Record) -> ProjectTruth:
    return ProjectTruth(
        truth_id=str(payload["truth_id"]),
        owner_id=str(payload["owner_id"]),
        project_id=str(payload["project_id"]),
        kind=TruthKind(str(payload["kind"])),
        statement=str(payload["statement"]),
        created_at=_dt(payload["created_at"]),
        source_ref=_optional(payload.get("source_ref")),
        evidence_refs=_strings(payload.get("evidence_refs", [])),
        supersedes_truth_id=_optional(payload.get("supersedes_truth_id")),
    )


def _evidence_payload(value: EvidenceItem) -> dict[str, Any]:
    return {
        "evidence_id": value.evidence_id,
        "owner_id": value.owner_id,
        "project_id": value.project_id,
        "kind": value.kind.value,
        "status": value.status.value,
        "source_locator": value.source_locator,
        "captured_at": value.captured_at.isoformat(),
        "content_hash": value.content_hash,
        "observed_facts": list(value.observed_facts),
        "limitations": list(value.limitations),
        "artifact_refs": list(value.artifact_refs),
        "applicable_platforms": list(value.applicable_platforms),
        "applicable_regions": list(value.applicable_regions),
        "source_updated_label": value.source_updated_label,
        "expires_at": value.expires_at.isoformat() if value.expires_at else None,
        "supersedes_evidence_id": value.supersedes_evidence_id,
    }


def _evidence_from(payload: _Record) -> EvidenceItem:
    raw_expires_at = payload.get("expires_at")
    return EvidenceItem(
        evidence_id=str(payload["evidence_id"]),
        owner_id=str(payload["owner_id"]),
        project_id=str(payload["project_id"]),
        kind=EvidenceKind(str(payload["kind"])),
        status=EvidenceStatus(str(payload["status"])),
        source_locator=str(payload["source_locator"]),
        captured_at=_dt(payload["captured_at"]),
        content_hash=str(payload["content_hash"]),
        observed_facts=_strings(payload.get("observed_facts", [])),
        limitations=_strings(payload.get("limitations", [])),
        artifact_refs=_strings(payload.get("artifact_refs", [])),
        applicable_platforms=_strings(payload.get("applicable_platforms", [])),
        applicable_regions=_strings(payload.get("applicable_regions", [])),
        source_updated_label=_optional(payload.get("source_updated_label")),
        expires_at=None if raw_expires_at is None else _dt(raw_expires_at),
        supersedes_evidence_id=_optional(payload.get("supersedes_evidence_id")),
    )


def _brief_payload(value: IncubationBrief) -> dict[str, Any]:
    return {
        "brief_version_id": value.brief_version_id,
        "brief_id": value.brief_id,
        "version": value.version,
        "owner_id": value.owner_id,
        "project_id": value.project_id,
        "created_at": value.created_at.isoformat(),
        "subject_kind": value.subject_kind.value if value.subject_kind else None,
        "subject_summary": value.subject_summary,
        "available_assets": list(value.available_assets),
        "capabilities": list(value.capabilities),
        "offers": list(value.offers),
        "constraints": list(value.constraints),
        "goals": list(value.goals),
        "truth_ids": list(value.truth_ids),
        "unknowns": list(value.unknowns),
        "supersedes_brief_version_id": value.supersedes_brief_version_id,
    }


def _brief_from(payload: _Record) -> IncubationBrief:
    raw_kind = payload["subject_kind"]
    return IncubationBrief(
        brief_version_id=str(payload["brief_version_id"]),
        brief_id=str(payload["brief_id"]),
        version=int(payload["version"]),
        owner_id=str(payload["owner_id"]),
        project_id=str(payload["project_id"]),
        created_at=_dt(payload["created_at"]),
        subject_kind=None if raw_kind is None else SubjectKind(str(raw_kind)),
        subject_summary=_optional(payload.get("subject_summary")),
        available_assets=_strings(payload.get("available_assets", [])),
        capabilities=_strings(payload.get("capabilities", [])),
        offers=_strings(payload.get("offers", [])),
        constraints=_strings(payload.get("constraints", [])),
        goals=_strings(payload.get("goals", [])),
        truth_ids=_strings(payload.get("truth_ids", [])),
        unknowns=_strings(payload.get("unknowns", [])),
        supersedes_brief_version_id=_optional(payload.get("supersedes_brief_version_id")),
    )


def _basis_payload(value: DecisionBasis) -> dict[str, Any]:
    return {
        "truth_ids": list(value.truth_ids),
        "rationale": list(value.rationale),
        "unknowns": list(value.unknowns),
        "alternatives": list(value.alternatives),
        "confidence": value.confidence,
    }


def _basis_from(value: object) -> DecisionBasis:
    if not isinstance(value, Mapping):
        raise TypeError("decision basis must be an object")
    raw_confidence = value.get("confidence")
    return DecisionBasis(
        truth_ids=_strings(value.get("truth_ids", [])),
        rationale=_strings(value.get("rationale", [])),
        unknowns=_strings(value.get("unknowns", [])),
        alternatives=_strings(value.get("alternatives", [])),
        confidence=None if raw_confidence is None else float(raw_confidence),
    )


def _territory_payload(value: TerritoryCandidate) -> dict[str, Any]:
    return {
        "territory_id": value.territory_id,
        "statement": value.statement,
        "lens_refs": list(value.lens_refs),
        "semantic_bridge": list(value.semantic_bridge),
        "recurring_situations": list(value.recurring_situations),
        "ownership_basis": list(value.ownership_basis),
        "attribution_path": value.attribution_path,
        "truth_ids": list(value.truth_ids),
        "evidence_refs": list(value.evidence_refs),
        "unknowns": list(value.unknowns),
    }


def _territory_from(value: object) -> TerritoryCandidate:
    if not isinstance(value, Mapping):
        raise TypeError("territory candidate must be an object")
    return TerritoryCandidate(
        territory_id=str(value["territory_id"]),
        statement=str(value["statement"]),
        lens_refs=_strings(value.get("lens_refs", [])),
        semantic_bridge=_strings(value.get("semantic_bridge", [])),
        recurring_situations=_strings(value.get("recurring_situations", [])),
        ownership_basis=_strings(value.get("ownership_basis", [])),
        attribution_path=_optional(value.get("attribution_path")),
        truth_ids=_strings(value.get("truth_ids", [])),
        evidence_refs=_strings(value.get("evidence_refs", [])),
        unknowns=_strings(value.get("unknowns", [])),
    )


def _territories_from(value: object) -> tuple[TerritoryCandidate, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("territory candidates must be a list")
    return tuple(_territory_from(candidate) for candidate in value)


def _decision_payload(value: IncubationDecisionVersion) -> dict[str, Any]:
    return {
        "decision_version_id": value.decision_version_id,
        "decision_id": value.decision_id,
        "version": value.version,
        "owner_id": value.owner_id,
        "project_id": value.project_id,
        "created_at": value.created_at.isoformat(),
        "basis": _basis_payload(value.basis),
        "subject": value.subject,
        "expression_carrier": value.expression_carrier,
        "intended_public": value.intended_public,
        "audience_problem": value.audience_problem,
        "value_promise": value.value_promise,
        "trust_evidence": list(value.trust_evidence),
        "format_plan": value.format_plan,
        "content_engine": value.content_engine,
        "monetization_path": value.monetization_path,
        "conversion_path": value.conversion_path,
        "first_experiment_id": value.first_experiment_id,
        "supersedes_decision_version_id": value.supersedes_decision_version_id,
        "territory_candidates": [_territory_payload(candidate) for candidate in value.territory_candidates],
        "selected_territory_id": value.selected_territory_id,
    }


def _decision_from(payload: _Record) -> IncubationDecisionVersion:
    return IncubationDecisionVersion(
        decision_version_id=str(payload["decision_version_id"]),
        decision_id=str(payload["decision_id"]),
        version=int(payload["version"]),
        owner_id=str(payload["owner_id"]),
        project_id=str(payload["project_id"]),
        created_at=_dt(payload["created_at"]),
        basis=_basis_from(payload["basis"]),
        subject=_optional(payload.get("subject")),
        expression_carrier=_optional(payload.get("expression_carrier")),
        intended_public=_optional(payload.get("intended_public")),
        audience_problem=_optional(payload.get("audience_problem")),
        value_promise=_optional(payload.get("value_promise")),
        trust_evidence=_strings(payload.get("trust_evidence", [])),
        format_plan=_optional(payload.get("format_plan")),
        content_engine=_optional(payload.get("content_engine")),
        monetization_path=_optional(payload.get("monetization_path")),
        conversion_path=_optional(payload.get("conversion_path")),
        first_experiment_id=_optional(payload.get("first_experiment_id")),
        supersedes_decision_version_id=_optional(payload.get("supersedes_decision_version_id")),
        territory_candidates=_territories_from(payload.get("territory_candidates", [])),
        selected_territory_id=_optional(payload.get("selected_territory_id")),
    )


def _experiment_payload(value: IncubationExperiment) -> dict[str, Any]:
    return {
        "experiment_id": value.experiment_id,
        "owner_id": value.owner_id,
        "project_id": value.project_id,
        "decision_version_id": value.decision_version_id,
        "created_at": value.created_at.isoformat(),
        "hypothesis": value.hypothesis,
        "content_variable": value.content_variable,
        "platform": value.platform,
        "format_name": value.format_name,
        "cost_cap": value.cost_cap,
        "currency": value.currency,
        "observation_window": value.observation_window,
        "success_signals": list(value.success_signals),
        "failure_signals": list(value.failure_signals),
    }


def _experiment_from(payload: _Record) -> IncubationExperiment:
    raw_cost = payload.get("cost_cap")
    return IncubationExperiment(
        experiment_id=str(payload["experiment_id"]),
        owner_id=str(payload["owner_id"]),
        project_id=str(payload["project_id"]),
        decision_version_id=str(payload["decision_version_id"]),
        created_at=_dt(payload["created_at"]),
        hypothesis=_optional(payload.get("hypothesis")),
        content_variable=_optional(payload.get("content_variable")),
        platform=_optional(payload.get("platform")),
        format_name=_optional(payload.get("format_name")),
        cost_cap=None if raw_cost is None else float(raw_cost),
        currency=_optional(payload.get("currency")),
        observation_window=_optional(payload.get("observation_window")),
        success_signals=_strings(payload.get("success_signals", [])),
        failure_signals=_strings(payload.get("failure_signals", [])),
    )


def _outcome_payload(value: OutcomeObservation) -> dict[str, Any]:
    return {
        "observation_id": value.observation_id,
        "owner_id": value.owner_id,
        "project_id": value.project_id,
        "experiment_id": value.experiment_id,
        "observed_at": value.observed_at.isoformat(),
        "observed_facts": list(value.observed_facts),
        "metrics": dict(value.metrics),
        "audience_signals": list(value.audience_signals),
        "commercial_signals": list(value.commercial_signals),
        "limitations": list(value.limitations),
        "evidence_refs": list(value.evidence_refs),
    }


def _outcome_from(payload: _Record) -> OutcomeObservation:
    metrics = payload.get("metrics", {})
    if not isinstance(metrics, Mapping):
        raise TypeError("outcome metrics must be an object")
    return OutcomeObservation(
        observation_id=str(payload["observation_id"]),
        owner_id=str(payload["owner_id"]),
        project_id=str(payload["project_id"]),
        experiment_id=str(payload["experiment_id"]),
        observed_at=_dt(payload["observed_at"]),
        observed_facts=_strings(payload.get("observed_facts", [])),
        metrics=dict(metrics),
        audience_signals=_strings(payload.get("audience_signals", [])),
        commercial_signals=_strings(payload.get("commercial_signals", [])),
        limitations=_strings(payload.get("limitations", [])),
        evidence_refs=_strings(payload.get("evidence_refs", [])),
    )


def _learning_payload(value: LearningDecision) -> dict[str, Any]:
    return {
        "learning_decision_id": value.learning_decision_id,
        "owner_id": value.owner_id,
        "project_id": value.project_id,
        "experiment_id": value.experiment_id,
        "action": value.action.value if value.action else None,
        "observation_ids": list(value.observation_ids),
        "rationale": list(value.rationale),
        "created_at": value.created_at.isoformat(),
        "next_experiment": value.next_experiment,
    }


def _learning_from(payload: _Record) -> LearningDecision:
    raw_action = payload.get("action")
    return LearningDecision(
        learning_decision_id=str(payload["learning_decision_id"]),
        owner_id=str(payload["owner_id"]),
        project_id=str(payload["project_id"]),
        experiment_id=str(payload["experiment_id"]),
        action=None if raw_action is None else LearningAction(str(raw_action)),
        observation_ids=_strings(payload.get("observation_ids", [])),
        rationale=_strings(payload.get("rationale", [])),
        created_at=_dt(payload["created_at"]),
        next_experiment=_optional(payload.get("next_experiment")),
    )


def _case_payload(value: CaseEpisode) -> dict[str, Any]:
    return {
        "case_episode_id": value.case_episode_id,
        "owner_id": value.owner_id,
        "project_id": value.project_id,
        "subject_kind": value.subject_kind.value,
        "status": value.status.value,
        "decision_version_id": value.decision_version_id,
        "outcome_observation_ids": list(value.outcome_observation_ids),
        "reviewed_by": value.reviewed_by,
        "reviewed_at": value.reviewed_at.isoformat() if value.reviewed_at else None,
        "created_at": value.created_at.isoformat(),
        "experiment_ids": list(value.experiment_ids),
        "learning_decision_ids": list(value.learning_decision_ids),
        "conditions": list(value.conditions),
        "tags": list(value.tags),
        "platforms": list(value.platforms),
        "supports_claims": list(value.supports_claims),
        "contradicts_claims": list(value.contradicts_claims),
        "limitations": list(value.limitations),
        "supersedes_case_episode_id": value.supersedes_case_episode_id,
        "cross_project_eligible": value.cross_project_eligible,
    }


def _case_from(payload: _Record) -> CaseEpisode:
    raw_reviewed_at = payload.get("reviewed_at")
    return CaseEpisode(
        case_episode_id=str(payload["case_episode_id"]),
        owner_id=str(payload["owner_id"]),
        project_id=str(payload["project_id"]),
        subject_kind=SubjectKind(str(payload["subject_kind"])),
        status=CaseStatus(str(payload["status"])),
        decision_version_id=str(payload["decision_version_id"]),
        outcome_observation_ids=_strings(payload["outcome_observation_ids"]),
        reviewed_by=_optional(payload.get("reviewed_by")),
        reviewed_at=None if raw_reviewed_at is None else _dt(raw_reviewed_at),
        created_at=_dt(payload["created_at"]),
        experiment_ids=_strings(payload.get("experiment_ids", [])),
        learning_decision_ids=_strings(payload.get("learning_decision_ids", [])),
        conditions=_strings(payload.get("conditions", [])),
        tags=_strings(payload.get("tags", [])),
        platforms=_strings(payload.get("platforms", [])),
        supports_claims=_strings(payload.get("supports_claims", [])),
        contradicts_claims=_strings(payload.get("contradicts_claims", [])),
        limitations=_strings(payload.get("limitations", [])),
        supersedes_case_episode_id=_optional(payload.get("supersedes_case_episode_id")),
        cross_project_eligible=bool(payload.get("cross_project_eligible", False)),
    )


class IncubationRepository:
    """Persist facts and versions while leaving marketing judgment to the agent."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def _run_idempotent(
        self,
        *,
        owner_id: str,
        operation_key: str,
        result_kind: str,
        result_id: str,
        request_payload: Mapping[str, Any],
        work: Callable[[AsyncSession], Awaitable[_T]],
        dump: Callable[[_T], dict[str, Any]],
        load: Callable[[_Record], _T],
    ) -> _T:
        if not operation_key.strip():
            raise ValueError("operation_key cannot be blank")
        digest = sha256(
            json.dumps(
                {"kind": result_kind, "request": request_payload},
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        async with self._session_factory.begin() as session:
            receipt = (
                (
                    await session.execute(
                        select(incubation_operation_receipts).where(
                            incubation_operation_receipts.c.owner_id == owner_id,
                            incubation_operation_receipts.c.operation_key == operation_key,
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
            if receipt is not None:
                if receipt["request_hash"] != digest or receipt["result_kind"] != result_kind:
                    raise IdempotencyConflict("operation_key was already used for a different request")
                payload = receipt["result_payload"]
                if not isinstance(payload, Mapping):
                    raise TypeError("operation receipt payload is malformed")
                return load(payload)
            result = await work(session)
            result_payload = dump(result)
            await session.execute(
                insert(incubation_operation_receipts).values(
                    owner_id=owner_id,
                    operation_key=operation_key,
                    request_hash=digest,
                    result_kind=result_kind,
                    result_id=result_id,
                    result_payload=result_payload,
                    created_at=datetime.now(UTC),
                )
            )
            return result

    async def create_project(
        self,
        project: IncubationProject,
        *,
        operation_key: str,
    ) -> IncubationProject:
        payload = _project_payload(project)

        async def work(session: AsyncSession) -> IncubationProject:
            existing = await self._payload_row(
                session,
                table=incubation_projects,
                id_column="project_id",
                owner_id=project.owner_id,
                identity=project.project_id,
            )
            if existing is not None:
                stored = _project_from(existing)
                if _project_payload(stored) != payload:
                    raise ImmutableRecordConflict("project identity already has different content")
                return stored
            await session.execute(
                insert(incubation_projects).values(
                    owner_id=project.owner_id,
                    project_id=project.project_id,
                    subject_kind=(project.subject_kind.value if project.subject_kind else None),
                    created_at=project.created_at,
                    payload=payload,
                )
            )
            return project

        return await self._run_idempotent(
            owner_id=project.owner_id,
            operation_key=operation_key,
            result_kind="project",
            result_id=project.project_id,
            request_payload=payload,
            work=work,
            dump=_project_payload,
            load=_project_from,
        )

    async def append_truth(
        self,
        truth: ProjectTruth,
        *,
        operation_key: str,
    ) -> ProjectTruth:
        payload = _truth_payload(truth)

        async def work(session: AsyncSession) -> ProjectTruth:
            await self._require_project(session, truth.owner_id, truth.project_id)
            if truth.supersedes_truth_id is not None:
                await self._require_ids(
                    session,
                    table=incubation_project_truths,
                    id_column="truth_id",
                    identities=(truth.supersedes_truth_id,),
                    owner_id=truth.owner_id,
                    project_id=truth.project_id,
                    label="superseded truth",
                )
            return await self._insert_immutable(
                session,
                table=incubation_project_truths,
                id_column="truth_id",
                identity=truth.truth_id,
                owner_id=truth.owner_id,
                payload=payload,
                load=_truth_from,
                values={
                    "owner_id": truth.owner_id,
                    "truth_id": truth.truth_id,
                    "project_id": truth.project_id,
                    "kind": truth.kind.value,
                    "created_at": truth.created_at,
                    "payload": payload,
                },
            )

        return await self._run_idempotent(
            owner_id=truth.owner_id,
            operation_key=operation_key,
            result_kind="truth",
            result_id=truth.truth_id,
            request_payload=payload,
            work=work,
            dump=_truth_payload,
            load=_truth_from,
        )

    async def append_evidence(
        self,
        evidence: EvidenceItem,
        *,
        operation_key: str,
    ) -> EvidenceItem:
        payload = _evidence_payload(evidence)

        async def work(session: AsyncSession) -> EvidenceItem:
            await self._require_project(session, evidence.owner_id, evidence.project_id)
            if evidence.supersedes_evidence_id is not None:
                await self._require_ids(
                    session,
                    table=incubation_evidence_items,
                    id_column="evidence_id",
                    identities=(evidence.supersedes_evidence_id,),
                    owner_id=evidence.owner_id,
                    project_id=evidence.project_id,
                    label="superseded evidence",
                )
            return await self._insert_immutable(
                session,
                table=incubation_evidence_items,
                id_column="evidence_id",
                identity=evidence.evidence_id,
                owner_id=evidence.owner_id,
                payload=payload,
                load=_evidence_from,
                values={
                    "owner_id": evidence.owner_id,
                    "evidence_id": evidence.evidence_id,
                    "project_id": evidence.project_id,
                    "kind": evidence.kind.value,
                    "status": evidence.status.value,
                    "captured_at": evidence.captured_at,
                    "payload": payload,
                },
            )

        return await self._run_idempotent(
            owner_id=evidence.owner_id,
            operation_key=operation_key,
            result_kind="evidence",
            result_id=evidence.evidence_id,
            request_payload=payload,
            work=work,
            dump=_evidence_payload,
            load=_evidence_from,
        )

    async def append_brief_version(
        self,
        brief: IncubationBrief,
        *,
        operation_key: str,
    ) -> IncubationBrief:
        payload = _brief_payload(brief)

        async def work(session: AsyncSession) -> IncubationBrief:
            await self._require_project(session, brief.owner_id, brief.project_id)
            await self._require_ids(
                session,
                table=incubation_project_truths,
                id_column="truth_id",
                identities=brief.truth_ids,
                owner_id=brief.owner_id,
                project_id=brief.project_id,
                label="brief truth",
            )
            await self._validate_version_lineage(
                session,
                table=incubation_brief_versions,
                owner_id=brief.owner_id,
                project_id=brief.project_id,
                series_column="brief_id",
                series_id=brief.brief_id,
                version=brief.version,
                version_id_column="brief_version_id",
                version_id=brief.brief_version_id,
                supersedes_id=brief.supersedes_brief_version_id,
            )
            return await self._insert_immutable(
                session,
                table=incubation_brief_versions,
                id_column="brief_version_id",
                identity=brief.brief_version_id,
                owner_id=brief.owner_id,
                payload=payload,
                load=_brief_from,
                values={
                    "owner_id": brief.owner_id,
                    "brief_version_id": brief.brief_version_id,
                    "brief_id": brief.brief_id,
                    "version": brief.version,
                    "project_id": brief.project_id,
                    "created_at": brief.created_at,
                    "payload": payload,
                },
            )

        return await self._run_idempotent(
            owner_id=brief.owner_id,
            operation_key=operation_key,
            result_kind="brief_version",
            result_id=brief.brief_version_id,
            request_payload=payload,
            work=work,
            dump=_brief_payload,
            load=_brief_from,
        )

    async def append_decision_version(
        self,
        decision: IncubationDecisionVersion,
        *,
        operation_key: str,
    ) -> IncubationDecisionVersion:
        payload = _decision_payload(decision)

        async def work(session: AsyncSession) -> IncubationDecisionVersion:
            await self._require_project(
                session,
                decision.owner_id,
                decision.project_id,
            )
            await self._require_ids(
                session,
                table=incubation_project_truths,
                id_column="truth_id",
                identities=tuple(
                    dict.fromkeys(
                        (
                            *decision.basis.truth_ids,
                            *decision.trust_evidence,
                            *(truth_id for candidate in decision.territory_candidates for truth_id in candidate.truth_ids),
                        )
                    )
                ),
                owner_id=decision.owner_id,
                project_id=decision.project_id,
                label="decision truth",
            )
            await self._require_ids(
                session,
                table=incubation_evidence_items,
                id_column="evidence_id",
                identities=tuple(dict.fromkeys(evidence_ref for candidate in decision.territory_candidates for evidence_ref in candidate.evidence_refs)),
                owner_id=decision.owner_id,
                project_id=decision.project_id,
                label="decision evidence",
            )
            await self._validate_version_lineage(
                session,
                table=incubation_decision_versions,
                owner_id=decision.owner_id,
                project_id=decision.project_id,
                series_column="decision_id",
                series_id=decision.decision_id,
                version=decision.version,
                version_id_column="decision_version_id",
                version_id=decision.decision_version_id,
                supersedes_id=decision.supersedes_decision_version_id,
            )
            return await self._insert_immutable(
                session,
                table=incubation_decision_versions,
                id_column="decision_version_id",
                identity=decision.decision_version_id,
                owner_id=decision.owner_id,
                payload=payload,
                load=_decision_from,
                values={
                    "owner_id": decision.owner_id,
                    "decision_version_id": decision.decision_version_id,
                    "decision_id": decision.decision_id,
                    "version": decision.version,
                    "project_id": decision.project_id,
                    "created_at": decision.created_at,
                    "payload": payload,
                },
            )

        return await self._run_idempotent(
            owner_id=decision.owner_id,
            operation_key=operation_key,
            result_kind="decision_version",
            result_id=decision.decision_version_id,
            request_payload=payload,
            work=work,
            dump=_decision_payload,
            load=_decision_from,
        )

    async def append_experiment(
        self,
        experiment: IncubationExperiment,
        *,
        operation_key: str,
    ) -> IncubationExperiment:
        payload = _experiment_payload(experiment)

        async def work(session: AsyncSession) -> IncubationExperiment:
            await self._require_project(
                session,
                experiment.owner_id,
                experiment.project_id,
            )
            await self._require_ids(
                session,
                table=incubation_decision_versions,
                id_column="decision_version_id",
                identities=(experiment.decision_version_id,),
                owner_id=experiment.owner_id,
                project_id=experiment.project_id,
                label="experiment decision",
            )
            return await self._insert_immutable(
                session,
                table=incubation_experiments,
                id_column="experiment_id",
                identity=experiment.experiment_id,
                owner_id=experiment.owner_id,
                payload=payload,
                load=_experiment_from,
                values={
                    "owner_id": experiment.owner_id,
                    "experiment_id": experiment.experiment_id,
                    "project_id": experiment.project_id,
                    "decision_version_id": experiment.decision_version_id,
                    "created_at": experiment.created_at,
                    "payload": payload,
                },
            )

        return await self._run_idempotent(
            owner_id=experiment.owner_id,
            operation_key=operation_key,
            result_kind="experiment",
            result_id=experiment.experiment_id,
            request_payload=payload,
            work=work,
            dump=_experiment_payload,
            load=_experiment_from,
        )

    async def append_outcome_observation(
        self,
        observation: OutcomeObservation,
        *,
        operation_key: str,
    ) -> OutcomeObservation:
        payload = _outcome_payload(observation)

        async def work(session: AsyncSession) -> OutcomeObservation:
            await self._require_project(
                session,
                observation.owner_id,
                observation.project_id,
            )
            await self._require_ids(
                session,
                table=incubation_experiments,
                id_column="experiment_id",
                identities=(observation.experiment_id,),
                owner_id=observation.owner_id,
                project_id=observation.project_id,
                label="outcome experiment",
            )
            return await self._insert_immutable(
                session,
                table=incubation_outcome_observations,
                id_column="observation_id",
                identity=observation.observation_id,
                owner_id=observation.owner_id,
                payload=payload,
                load=_outcome_from,
                values={
                    "owner_id": observation.owner_id,
                    "observation_id": observation.observation_id,
                    "project_id": observation.project_id,
                    "experiment_id": observation.experiment_id,
                    "observed_at": observation.observed_at,
                    "payload": payload,
                },
            )

        return await self._run_idempotent(
            owner_id=observation.owner_id,
            operation_key=operation_key,
            result_kind="outcome_observation",
            result_id=observation.observation_id,
            request_payload=payload,
            work=work,
            dump=_outcome_payload,
            load=_outcome_from,
        )

    async def append_learning_decision(
        self,
        learning: LearningDecision,
        *,
        operation_key: str,
    ) -> LearningDecision:
        payload = _learning_payload(learning)

        async def work(session: AsyncSession) -> LearningDecision:
            await self._require_project(
                session,
                learning.owner_id,
                learning.project_id,
            )
            await self._require_ids(
                session,
                table=incubation_experiments,
                id_column="experiment_id",
                identities=(learning.experiment_id,),
                owner_id=learning.owner_id,
                project_id=learning.project_id,
                label="learning experiment",
            )
            await self._require_ids(
                session,
                table=incubation_outcome_observations,
                id_column="observation_id",
                identities=learning.observation_ids,
                owner_id=learning.owner_id,
                project_id=learning.project_id,
                label="learning observation",
            )
            return await self._insert_immutable(
                session,
                table=incubation_learning_decisions,
                id_column="learning_decision_id",
                identity=learning.learning_decision_id,
                owner_id=learning.owner_id,
                payload=payload,
                load=_learning_from,
                values={
                    "owner_id": learning.owner_id,
                    "learning_decision_id": learning.learning_decision_id,
                    "project_id": learning.project_id,
                    "experiment_id": learning.experiment_id,
                    "created_at": learning.created_at,
                    "payload": payload,
                },
            )

        return await self._run_idempotent(
            owner_id=learning.owner_id,
            operation_key=operation_key,
            result_kind="learning_decision",
            result_id=learning.learning_decision_id,
            request_payload=payload,
            work=work,
            dump=_learning_payload,
            load=_learning_from,
        )

    async def append_case_episode(
        self,
        case: CaseEpisode,
        *,
        operation_key: str,
    ) -> CaseEpisode:
        payload = _case_payload(case)

        async def work(session: AsyncSession) -> CaseEpisode:
            await self._require_project(session, case.owner_id, case.project_id)
            references: tuple[tuple[Table, str, Sequence[str], str], ...] = (
                (
                    incubation_decision_versions,
                    "decision_version_id",
                    (case.decision_version_id,),
                    "case decision",
                ),
                (
                    incubation_experiments,
                    "experiment_id",
                    case.experiment_ids,
                    "case experiment",
                ),
                (
                    incubation_outcome_observations,
                    "observation_id",
                    case.outcome_observation_ids,
                    "case outcome",
                ),
                (
                    incubation_learning_decisions,
                    "learning_decision_id",
                    case.learning_decision_ids,
                    "case learning decision",
                ),
            )
            for table, id_column, identities, label in references:
                await self._require_ids(
                    session,
                    table=table,
                    id_column=id_column,
                    identities=identities,
                    owner_id=case.owner_id,
                    project_id=case.project_id,
                    label=label,
                )
            if case.supersedes_case_episode_id is not None:
                await self._require_ids(
                    session,
                    table=incubation_case_episodes,
                    id_column="case_episode_id",
                    identities=(case.supersedes_case_episode_id,),
                    owner_id=case.owner_id,
                    project_id=case.project_id,
                    label="superseded case",
                )
            return await self._insert_immutable(
                session,
                table=incubation_case_episodes,
                id_column="case_episode_id",
                identity=case.case_episode_id,
                owner_id=case.owner_id,
                payload=payload,
                load=_case_from,
                values={
                    "owner_id": case.owner_id,
                    "case_episode_id": case.case_episode_id,
                    "project_id": case.project_id,
                    "status": case.status.value,
                    "created_at": case.created_at,
                    "payload": payload,
                },
            )

        return await self._run_idempotent(
            owner_id=case.owner_id,
            operation_key=operation_key,
            result_kind="case_episode",
            result_id=case.case_episode_id,
            request_payload=payload,
            work=work,
            dump=_case_payload,
            load=_case_from,
        )

    async def list_current_truths(
        self,
        *,
        owner_id: str,
        project_id: str,
    ) -> list[ProjectTruth]:
        """Return the unsuperseded truth heads for one owner-scoped project."""
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(incubation_project_truths.c.payload)
                        .where(
                            incubation_project_truths.c.owner_id == owner_id,
                            incubation_project_truths.c.project_id == project_id,
                        )
                        .order_by(
                            incubation_project_truths.c.created_at,
                            incubation_project_truths.c.truth_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
        truths = [_truth_from(row) for row in rows]
        superseded_ids = {truth.supersedes_truth_id for truth in truths if truth.supersedes_truth_id is not None}
        return [truth for truth in truths if truth.truth_id not in superseded_ids]

    async def list_current_evidence(
        self,
        *,
        owner_id: str,
        project_id: str,
        platform: str | None = None,
        limit: int = 20,
    ) -> list[EvidenceItem]:
        """Return current evidence snapshots without promoting them to project truth."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        normalized_platform = platform.strip().casefold() if platform is not None else None
        if platform is not None and not normalized_platform:
            raise ValueError("platform cannot be blank when supplied")

        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(incubation_evidence_items.c.payload)
                        .where(
                            incubation_evidence_items.c.owner_id == owner_id,
                            incubation_evidence_items.c.project_id == project_id,
                        )
                        .order_by(
                            incubation_evidence_items.c.captured_at,
                            incubation_evidence_items.c.evidence_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
        evidence_items = [_evidence_from(row) for row in rows]
        superseded_ids = {item.supersedes_evidence_id for item in evidence_items if item.supersedes_evidence_id is not None}
        current = [
            item
            for item in evidence_items
            if item.evidence_id not in superseded_ids
            and item.status in {EvidenceStatus.ACTIVE, EvidenceStatus.CONTESTED}
            and (normalized_platform is None or not item.applicable_platforms or normalized_platform in {value.casefold() for value in item.applicable_platforms})
        ]
        current.reverse()
        return current[:limit]

    async def get_current_brief(
        self,
        *,
        owner_id: str,
        project_id: str,
        brief_id: str,
    ) -> IncubationBrief | None:
        return await self._get_current_version(
            table=incubation_brief_versions,
            owner_id=owner_id,
            project_id=project_id,
            series_column="brief_id",
            series_id=brief_id,
            load=_brief_from,
        )

    async def get_current_decision(
        self,
        *,
        owner_id: str,
        project_id: str,
        decision_id: str,
    ) -> IncubationDecisionVersion | None:
        return await self._get_current_version(
            table=incubation_decision_versions,
            owner_id=owner_id,
            project_id=project_id,
            series_column="decision_id",
            series_id=decision_id,
            load=_decision_from,
        )

    async def list_case_episodes(
        self,
        *,
        owner_id: str,
        project_id: str,
    ) -> list[CaseEpisode]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(incubation_case_episodes.c.payload)
                        .where(
                            incubation_case_episodes.c.owner_id == owner_id,
                            incubation_case_episodes.c.project_id == project_id,
                        )
                        .order_by(
                            incubation_case_episodes.c.created_at,
                            incubation_case_episodes.c.case_episode_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
        return [_case_from(row) for row in rows]

    async def _get_current_version(
        self,
        *,
        table: Table,
        owner_id: str,
        project_id: str,
        series_column: str,
        series_id: str,
        load: Callable[[_Record], _T],
    ) -> _T | None:
        async with self._session_factory() as session:
            payload = await session.scalar(
                select(table.c.payload)
                .where(
                    table.c.owner_id == owner_id,
                    table.c.project_id == project_id,
                    table.c[series_column] == series_id,
                )
                .order_by(table.c.version.desc())
                .limit(1)
            )
        if payload is None:
            return None
        if not isinstance(payload, Mapping):
            raise TypeError("stored version payload is malformed")
        return load(payload)

    async def _payload_row(
        self,
        session: AsyncSession,
        *,
        table: Table,
        id_column: str,
        owner_id: str,
        identity: str,
    ) -> Mapping[str, Any] | None:
        payload = await session.scalar(
            select(table.c.payload).where(
                table.c.owner_id == owner_id,
                table.c[id_column] == identity,
            )
        )
        if payload is None:
            return None
        if not isinstance(payload, Mapping):
            raise TypeError("stored payload is malformed")
        return payload

    async def _require_project(
        self,
        session: AsyncSession,
        owner_id: str,
        project_id: str,
    ) -> None:
        payload = await self._payload_row(
            session,
            table=incubation_projects,
            id_column="project_id",
            owner_id=owner_id,
            identity=project_id,
        )
        if payload is None:
            raise OwnershipViolation("project does not exist for this owner")

    async def _require_ids(
        self,
        session: AsyncSession,
        *,
        table: Table,
        id_column: str,
        identities: Sequence[str],
        owner_id: str,
        project_id: str,
        label: str,
    ) -> None:
        requested = tuple(dict.fromkeys(identities))
        if not requested:
            return
        found = set(
            (
                await session.scalars(
                    select(table.c[id_column]).where(
                        table.c.owner_id == owner_id,
                        table.c.project_id == project_id,
                        table.c[id_column].in_(requested),
                    )
                )
            ).all()
        )
        missing = set(requested) - found
        if missing:
            raise OwnershipViolation(f"{label} does not exist in this owner/project: {sorted(missing)}")

    async def _insert_immutable(
        self,
        session: AsyncSession,
        *,
        table: Table,
        id_column: str,
        identity: str,
        owner_id: str,
        payload: Mapping[str, Any],
        load: Callable[[_Record], _T],
        values: Mapping[str, Any],
    ) -> _T:
        existing = await self._payload_row(
            session,
            table=table,
            id_column=id_column,
            owner_id=owner_id,
            identity=identity,
        )
        if existing is not None:
            stored = load(existing)
            if existing != payload:
                raise ImmutableRecordConflict(f"{id_column} already has different immutable content")
            return stored
        await session.execute(insert(table).values(**values))
        return load(payload)

    async def _validate_version_lineage(
        self,
        session: AsyncSession,
        *,
        table: Table,
        owner_id: str,
        project_id: str,
        series_column: str,
        series_id: str,
        version: int,
        version_id_column: str,
        version_id: str,
        supersedes_id: str | None,
    ) -> None:
        existing_id = await session.scalar(
            select(table.c[version_id_column]).where(
                table.c.owner_id == owner_id,
                table.c.project_id == project_id,
                table.c[series_column] == series_id,
                table.c.version == version,
            )
        )
        if existing_id is not None:
            if str(existing_id) != version_id:
                raise ImmutableRecordConflict("version number already belongs to a different immutable identity")
            return
        previous = (
            (
                await session.execute(
                    select(
                        table.c.version,
                        table.c[version_id_column],
                    )
                    .where(
                        table.c.owner_id == owner_id,
                        table.c.project_id == project_id,
                        table.c[series_column] == series_id,
                    )
                    .order_by(table.c.version.desc())
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        if previous is None:
            if version != 1 or supersedes_id is not None:
                raise ImmutableRecordConflict("the first version must be version 1 without a predecessor")
            return
        if version != int(previous["version"]) + 1:
            raise ImmutableRecordConflict("version lineage must be contiguous")
        if supersedes_id != str(previous[version_id_column]):
            raise ImmutableRecordConflict("new version must supersede the current version identity")


__all__ = [
    "IdempotencyConflict",
    "ImmutableRecordConflict",
    "IncubationRepository",
    "OwnershipViolation",
]
