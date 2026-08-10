from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
import pytest_asyncio
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
from mcn_incubation.persistence import (
    IdempotencyConflict,
    ImmutableRecordConflict,
    IncubationRepository,
    OwnershipViolation,
)
from mcn_incubation.persistence_schema import (
    CURRENT_INCUBATION_SCHEMA_VERSION,
    bootstrap_incubation_schema,
    incubation_evidence_items,
    incubation_metadata,
    incubation_schema_versions,
    read_incubation_schema_version,
)
from sqlalchemy import insert, inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
EXPECTED_TABLES = {
    "incubation_schema_versions",
    "incubation_projects",
    "incubation_operation_receipts",
    "incubation_evidence_items",
    "incubation_project_truths",
    "incubation_brief_versions",
    "incubation_decision_versions",
    "incubation_experiments",
    "incubation_outcome_observations",
    "incubation_learning_decisions",
    "incubation_case_episodes",
}


@pytest_asyncio.fixture
async def repository(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'incubation.db'}")
    await bootstrap_incubation_schema(engine)
    repo = IncubationRepository(async_sessionmaker(engine, expire_on_commit=False))
    yield repo, engine
    await engine.dispose()


def _project() -> IncubationProject:
    return IncubationProject(
        project_id="project-a",
        owner_id="owner-a",
        working_title="会计宝妈起号",
        subject_kind=SubjectKind.PERSON,
        created_at=NOW,
    )


def _truth() -> ProjectTruth:
    return ProjectTruth(
        truth_id="truth-career",
        owner_id="owner-a",
        project_id="project-a",
        kind=TruthKind.USER_FACT,
        statement="本人有十年企业会计经验",
        created_at=NOW,
    )


def _evidence(
    *,
    evidence_id: str = "evidence-a",
    supersedes_evidence_id: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        owner_id="owner-a",
        project_id="project-a",
        kind=EvidenceKind.PUBLIC_PROFILE,
        status=EvidenceStatus.ACTIVE,
        source_locator="https://example.test/profile",
        captured_at=NOW,
        content_hash=("a" if evidence_id == "evidence-a" else "b") * 64,
        observed_facts=("主页公开展示三个置顶作品",),
        limitations=("未检查全部历史作品",),
        applicable_platforms=("xiaohongshu",),
        supersedes_evidence_id=supersedes_evidence_id,
    )


def _brief() -> IncubationBrief:
    return IncubationBrief(
        brief_version_id="brief-v1",
        brief_id="brief-a",
        version=1,
        owner_id="owner-a",
        project_id="project-a",
        created_at=NOW,
        subject_kind=SubjectKind.PERSON,
        subject_summary="有会计经验的宝妈",
        truth_ids=("truth-career",),
        constraints=("不展示孩子",),
        goals=("验证财务咨询需求",),
    )


def _decision() -> IncubationDecisionVersion:
    return IncubationDecisionVersion(
        decision_version_id="decision-v1",
        decision_id="decision-a",
        version=1,
        owner_id="owner-a",
        project_id="project-a",
        created_at=NOW,
        subject="有十年会计经验的宝妈",
        expression_carrier="本人加桌面账本",
        intended_public="小生意经营者",
        audience_problem="看不懂现金流",
        value_promise="用一页账本讲清一个经营问题",
        trust_evidence=("truth-career",),
        format_plan="本人旁白加手写账本",
        content_engine="每期拆一个真实经营误区",
        monetization_path="财务体检到月度顾问",
        conversion_path="内容到模板到诊断",
        first_experiment_id="experiment-a",
        basis=DecisionBasis(
            truth_ids=("truth-career",),
            rationale=("职业事实支撑专业判断",),
            unknowns=("镜头表现未知",),
            alternatives=("只拍手部",),
            confidence=0.5,
        ),
    )


def _experiment() -> IncubationExperiment:
    return IncubationExperiment(
        experiment_id="experiment-a",
        owner_id="owner-a",
        project_id="project-a",
        decision_version_id="decision-v1",
        created_at=NOW,
        hypothesis="真实账本拆解能产生具体咨询问题",
        content_variable="本人出镜与只拍手部",
        success_signals=("收到具体财务问题",),
    )


def _outcome() -> OutcomeObservation:
    return OutcomeObservation(
        observation_id="observation-a",
        owner_id="owner-a",
        project_id="project-a",
        experiment_id="experiment-a",
        observed_at=NOW,
        observed_facts=("收到 3 条具体财务问题",),
        metrics={"qualified_questions": 3},
        limitations=("只有一条内容",),
    )


@pytest.mark.asyncio
async def test_schema_is_independent_and_contains_only_new_incubation_tables(repository) -> None:
    _repo, engine = repository
    async with engine.connect() as connection:
        table_names = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))

    assert incubation_metadata is not None
    assert table_names == EXPECTED_TABLES
    assert all("marketing" not in table_name for table_name in table_names)
    assert await read_incubation_schema_version(engine) == CURRENT_INCUBATION_SCHEMA_VERSION == 2


@pytest.mark.asyncio
async def test_schema_bootstrap_upgrades_additive_v1_evidence_table(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'incubation-v1.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda sync: incubation_schema_versions.create(sync))
            await connection.execute(
                insert(incubation_schema_versions).values(
                    component="mcn-incubation-core",
                    version=1,
                    applied_at=NOW,
                )
            )

        await bootstrap_incubation_schema(engine)

        async with engine.connect() as connection:
            tables = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        assert incubation_evidence_items.name in tables
        assert await read_incubation_schema_version(engine) == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_truth_brief_and_decision_are_append_only_owner_scoped_truth(repository) -> None:
    repo, _engine = repository
    await repo.create_project(_project(), operation_key="create-project")
    await repo.append_truth(_truth(), operation_key="append-truth")
    await repo.append_brief_version(_brief(), operation_key="append-brief")
    decision = await repo.append_decision_version(_decision(), operation_key="append-decision")

    replay = await repo.append_decision_version(_decision(), operation_key="append-decision")

    assert replay == decision
    assert await repo.get_current_brief(owner_id="owner-a", project_id="project-a", brief_id="brief-a") == _brief()
    assert await repo.get_current_decision(owner_id="owner-a", project_id="project-a", decision_id="decision-a") == decision
    assert await repo.get_current_decision(owner_id="owner-b", project_id="project-a", decision_id="decision-a") is None


@pytest.mark.asyncio
async def test_current_truths_hide_superseded_history_without_crossing_owner_scope(repository) -> None:
    repo, _engine = repository
    await repo.create_project(_project(), operation_key="create-project")
    original = _truth()
    constraint = ProjectTruth(
        truth_id="truth-privacy",
        owner_id="owner-a",
        project_id="project-a",
        kind=TruthKind.USER_FACT,
        statement="不展示孩子",
        created_at=NOW,
    )
    correction = ProjectTruth(
        truth_id="truth-career-corrected",
        owner_id="owner-a",
        project_id="project-a",
        kind=TruthKind.USER_FACT,
        statement="本人有八年企业会计经验",
        created_at=NOW,
        supersedes_truth_id=original.truth_id,
    )
    final_correction = ProjectTruth(
        truth_id="truth-career-final",
        owner_id="owner-a",
        project_id="project-a",
        kind=TruthKind.USER_FACT,
        statement="本人有八年企业财务经验，其中五年负责小微企业",
        created_at=NOW,
        supersedes_truth_id=correction.truth_id,
    )

    for truth in (original, constraint, correction, final_correction):
        await repo.append_truth(truth, operation_key=f"append-{truth.truth_id}")

    assert await repo.list_current_truths(owner_id="owner-a", project_id="project-a") == [
        final_correction,
        constraint,
    ]
    assert await repo.list_current_truths(owner_id="owner-b", project_id="project-a") == []


@pytest.mark.asyncio
async def test_external_evidence_is_append_only_current_and_owner_scoped(repository) -> None:
    repo, _engine = repository
    await repo.create_project(_project(), operation_key="create-project")
    original = _evidence()
    replacement = _evidence(
        evidence_id="evidence-b",
        supersedes_evidence_id=original.evidence_id,
    )

    await repo.append_evidence(original, operation_key="append-evidence-a")
    await repo.append_evidence(replacement, operation_key="append-evidence-b")

    assert await repo.list_current_evidence(
        owner_id="owner-a",
        project_id="project-a",
        platform="xiaohongshu",
        limit=20,
    ) == [replacement]
    assert (
        await repo.list_current_evidence(
            owner_id="owner-b",
            project_id="project-a",
            limit=20,
        )
        == []
    )


@pytest.mark.asyncio
async def test_experiment_outcome_learning_and_reviewed_case_form_a_grounded_loop(repository) -> None:
    repo, _engine = repository
    await repo.create_project(_project(), operation_key="create-project")
    await repo.append_truth(_truth(), operation_key="append-truth")
    await repo.append_brief_version(_brief(), operation_key="append-brief")
    await repo.append_decision_version(_decision(), operation_key="append-decision")
    experiment = await repo.append_experiment(_experiment(), operation_key="append-experiment")
    outcome = await repo.append_outcome_observation(_outcome(), operation_key="append-outcome")
    learning = LearningDecision(
        learning_decision_id="learning-a",
        owner_id="owner-a",
        project_id="project-a",
        experiment_id="experiment-a",
        action=LearningAction.REVISE,
        observation_ids=("observation-a",),
        rationale=("继续测试，但不要从单条结果推出通用规律",),
        created_at=NOW,
    )
    await repo.append_learning_decision(learning, operation_key="append-learning")
    case = CaseEpisode(
        case_episode_id="case-a",
        owner_id="owner-a",
        project_id="project-a",
        subject_kind=SubjectKind.PERSON,
        status=CaseStatus.ACTIVE,
        decision_version_id="decision-v1",
        experiment_ids=("experiment-a",),
        outcome_observation_ids=("observation-a",),
        learning_decision_ids=("learning-a",),
        conditions=("有会计职业证据", "不展示孩子"),
        supports_claims=("职业事实可以成为内容发动机",),
        limitations=("单条内容不能外推",),
        reviewed_by="operator-a",
        reviewed_at=NOW,
        created_at=NOW,
    )
    stored_case = await repo.append_case_episode(case, operation_key="append-case")

    assert experiment == _experiment()
    assert outcome == _outcome()
    assert stored_case == case
    assert await repo.list_case_episodes(owner_id="owner-a", project_id="project-a") == [case]
    assert await repo.list_case_episodes(owner_id="owner-b", project_id="project-a") == []


@pytest.mark.asyncio
async def test_owner_idempotency_and_version_identity_conflicts_are_domain_errors(repository) -> None:
    repo, _engine = repository
    await repo.create_project(_project(), operation_key="create-project")

    with pytest.raises(OwnershipViolation):
        await repo.append_truth(
            replace(_truth(), owner_id="owner-b"),
            operation_key="owner-b-append-truth",
        )

    await repo.append_truth(_truth(), operation_key="append-truth")
    with pytest.raises(IdempotencyConflict):
        await repo.append_truth(
            replace(_truth(), truth_id="different-truth"),
            operation_key="append-truth",
        )

    await repo.append_decision_version(_decision(), operation_key="append-decision")
    with pytest.raises(ImmutableRecordConflict):
        await repo.append_decision_version(
            replace(_decision(), decision_version_id="decision-v1-other"),
            operation_key="append-conflicting-decision-version",
        )
