from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
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
    TruthKind,
)

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def test_partial_brief_and_decision_surface_unknowns_without_blocking_work() -> None:
    brief = IncubationBrief(
        brief_version_id="brief-v1",
        brief_id="brief-a",
        version=1,
        owner_id="owner-a",
        project_id="project-a",
        created_at=NOW,
        subject_kind=SubjectKind.PERSON,
        constraints=("不能拍孩子",),
    )
    decision = IncubationDecisionVersion(
        decision_version_id="decision-v1",
        decision_id="decision-a",
        version=1,
        owner_id="owner-a",
        project_id="project-a",
        created_at=NOW,
        basis=DecisionBasis(
            unknowns=("尚未确认可售产品",),
            alternatives=("先记录转型过程，再验证咨询需求",),
        ),
    )

    assert "subject_summary" in brief.missing_fields
    assert "goals" in brief.missing_fields
    assert "monetization_path" in decision.missing_fields
    assert "first_experiment_id" in decision.missing_fields
    assert decision.basis.confidence is None


def test_truth_ledger_never_collapses_fact_inference_hypothesis_and_unknown() -> None:
    kinds = {
        TruthKind.USER_FACT,
        TruthKind.SOURCE_FACT,
        TruthKind.INFERENCE,
        TruthKind.CREATIVE_HYPOTHESIS,
        TruthKind.UNKNOWN,
        TruthKind.APPROVED_DECISION,
        TruthKind.OBSERVED_OUTCOME,
    }

    assert {kind.value for kind in kinds} == {
        "user_fact",
        "source_fact",
        "inference",
        "creative_hypothesis",
        "unknown",
        "approved_decision",
        "observed_outcome",
    }

    truth = ProjectTruth(
        truth_id="truth-a",
        owner_id="owner-a",
        project_id="project-a",
        kind=TruthKind.USER_FACT,
        statement="本人不希望孩子出镜",
        created_at=NOW,
    )
    with pytest.raises(FrozenInstanceError):
        truth.statement = "changed"  # type: ignore[misc]


def test_experiment_outcome_and_learning_are_observations_not_marketing_gates() -> None:
    experiment = IncubationExperiment(
        experiment_id="experiment-a",
        owner_id="owner-a",
        project_id="project-a",
        decision_version_id="decision-v1",
        created_at=NOW,
        hypothesis="真实转型账本比泛育儿经验更容易建立可信度",
    )
    outcome = OutcomeObservation(
        observation_id="observation-a",
        owner_id="owner-a",
        project_id="project-a",
        experiment_id="experiment-a",
        observed_at=NOW,
        observed_facts=("收到 3 条关于转型路径的具体提问",),
        metrics={"qualified_questions": 3},
        limitations=("只有一条内容",),
    )
    learning = LearningDecision(
        learning_decision_id="learning-a",
        owner_id="owner-a",
        project_id="project-a",
        experiment_id="experiment-a",
        action=LearningAction.REVISE,
        observation_ids=("observation-a",),
        rationale=("问题集中在转型而不是育儿",),
        created_at=NOW,
    )

    assert "content_variable" in experiment.missing_fields
    assert outcome.metrics["qualified_questions"] == 3
    assert learning.action is LearningAction.REVISE


def test_external_evidence_keeps_snapshot_provenance_scope_and_limits() -> None:
    evidence = EvidenceItem(
        evidence_id="evidence-a",
        owner_id="owner-a",
        project_id="project-a",
        kind=EvidenceKind.OFFICIAL_PLATFORM_SNAPSHOT,
        status=EvidenceStatus.ACTIVE,
        source_locator="https://example.test/platform-rule",
        captured_at=NOW,
        content_hash="a" * 64,
        observed_facts=("页面说明商业内容需要披露合作关系",),
        limitations=("只适用于该页面标注的商业内容场景",),
        applicable_platforms=("tiktok",),
        applicable_regions=("US",),
        artifact_refs=("artifact://evidence-a.html",),
        expires_at=datetime(2026, 8, 17, 12, 0, tzinfo=UTC),
    )

    assert evidence.kind is EvidenceKind.OFFICIAL_PLATFORM_SNAPSHOT
    assert evidence.is_refresh_due(as_of=datetime(2026, 8, 18, tzinfo=UTC))
    assert evidence.observed_facts == ("页面说明商业内容需要披露合作关系",)

    with pytest.raises(ValueError, match="content_hash"):
        EvidenceItem(
            evidence_id="bad-hash",
            owner_id="owner-a",
            project_id="project-a",
            kind=EvidenceKind.PUBLIC_CONTENT,
            status=EvidenceStatus.ACTIVE,
            source_locator="https://example.test/content",
            captured_at=NOW,
            content_hash="not-a-sha256",
            observed_facts=("可见内容",),
            limitations=("指标不可见",),
        )


def test_case_memory_requires_observed_results_and_human_review() -> None:
    with pytest.raises(ValueError, match="observed outcome"):
        CaseEpisode(
            case_episode_id="case-a",
            owner_id="owner-a",
            project_id="project-a",
            subject_kind=SubjectKind.PERSON,
            status=CaseStatus.ACTIVE,
            decision_version_id="decision-v1",
            outcome_observation_ids=(),
            reviewed_by="operator-a",
            reviewed_at=NOW,
            created_at=NOW,
        )

    with pytest.raises(ValueError, match="human review"):
        CaseEpisode(
            case_episode_id="case-a",
            owner_id="owner-a",
            project_id="project-a",
            subject_kind=SubjectKind.PERSON,
            status=CaseStatus.ACTIVE,
            decision_version_id="decision-v1",
            outcome_observation_ids=("observation-a",),
            reviewed_by=None,
            reviewed_at=None,
            created_at=NOW,
        )


def test_project_name_is_a_working_label_not_a_frozen_product_brand() -> None:
    project = IncubationProject(
        project_id="project-a",
        owner_id="owner-a",
        working_title="宝妈转型起号实验",
        subject_kind=None,
        created_at=NOW,
    )

    assert project.subject_kind is None
    assert project.working_title == "宝妈转型起号实验"
