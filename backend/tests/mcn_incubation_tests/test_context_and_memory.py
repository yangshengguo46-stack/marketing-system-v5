from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from mcn_incubation.context import (
    ArchitectureVariant,
    ContextAssembler,
    ContextRequest,
)
from mcn_incubation.domain import (
    CaseEpisode,
    CaseStatus,
    IncubationBrief,
    ProjectTruth,
    SubjectKind,
    TruthKind,
)
from mcn_incubation.knowledge import (
    TIKTOK_COMMERCIAL_QUALITY_SOURCE_ID,
    XHS_MCN_INTRO_SOURCE_ID,
    KnowledgeSourceKind,
    UnknownKnowledgeSource,
    default_knowledge_catalog,
)
from mcn_incubation.memory import CaseMemory, CaseQuery
from mcn_incubation.methods import MethodLibrary, default_method_cards, default_method_library

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def _case(
    *,
    case_id: str,
    project_id: str,
    status: CaseStatus = CaseStatus.ACTIVE,
    supports: tuple[str, ...] = (),
    contradicts: tuple[str, ...] = (),
) -> CaseEpisode:
    return CaseEpisode(
        case_episode_id=case_id,
        owner_id="owner-a",
        project_id=project_id,
        subject_kind=SubjectKind.PERSON,
        status=status,
        decision_version_id=f"decision-{case_id}",
        outcome_observation_ids=(f"outcome-{case_id}",),
        conditions=("有职业经验", "不展示孩子"),
        tags=("宝妈", "知识服务", "口播"),
        supports_claims=supports,
        contradicts_claims=contradicts,
        limitations=("样本量小",),
        reviewed_by="operator-a",
        reviewed_at=NOW,
        created_at=NOW,
    )


def test_method_library_is_sourced_and_retrieved_on_demand() -> None:
    cards = default_method_cards()
    library = default_method_library()

    assert {
        "incubation_model",
        "positioning",
        "audience_problem",
        "trust_proof",
        "expression_form",
        "benchmark_adaptation",
        "content_engine",
        "monetization",
        "conversion",
        "experiment_design",
    }.issubset({card.capability for card in cards})
    assert all(card.source_refs for card in cards)

    selected = library.search(
        query="这位宝妈不让孩子出镜，应该用什么表现形式并且怎样持续更新",
        limit=3,
    )

    assert 1 <= len(selected) <= 3
    assert any(card.capability == "expression_form" for card in selected)
    assert len(selected) < len(cards)


def test_every_method_reference_resolves_to_reviewed_source_metadata() -> None:
    cards = default_method_cards()
    catalog = default_knowledge_catalog()
    referenced = {source_ref for card in cards for source_ref in card.source_refs}

    assert referenced == {source.source_id for source in catalog.sources}
    assert all(source.supported_claims for source in catalog.sources)
    assert all(source.limitations for source in catalog.sources)
    assert all(source.retrieved_at.tzinfo is not None for source in catalog.sources)
    assert all(source.reviewed_at.tzinfo is not None for source in catalog.sources)

    xhs = catalog.get(XHS_MCN_INTRO_SOURCE_ID)
    assert xhs.kind is KnowledgeSourceKind.OFFICIAL_PLATFORM
    assert xhs.applicable_platforms == ("xiaohongshu",)
    assert xhs.refresh_after is not None

    tiktok = catalog.get(TIKTOK_COMMERCIAL_QUALITY_SOURCE_ID)
    assert tiktok.kind is KnowledgeSourceKind.OFFICIAL_PLATFORM
    assert tiktok.applicable_platforms == ("tiktok",)
    assert "TikTok One" in " ".join(tiktok.limitations)


def test_method_library_rejects_unresolved_or_retired_source_instead_of_faking_provenance() -> None:
    card = replace(default_method_cards()[0], source_refs=("missing-source",))

    with pytest.raises(UnknownKnowledgeSource, match="missing-source"):
        MethodLibrary((card,), source_catalog=default_knowledge_catalog())


def test_method_cards_keep_assets_content_supply_and_thresholds_grounded() -> None:
    cards = {card.capability: card for card in default_method_cards()}

    assert "未确认的人物、场地、团队和素材只能作为待验证方案" in cards["expression_form"].lens
    assert any(value.startswith("常见或低制作成本不等于适合当前主体") for value in cards["expression_form"].lens)
    assert "主体的真实表达样本" in cards["expression_form"].evidence_needs
    assert "因为口播制作简单就默认真人露脸" in cards["expression_form"].counterexamples
    assert "公开配方不等于已证明安全性或效果" in cards["positioning"].counterexamples
    assert "内容供给必须来自已确认可持续获得的真实来源" in cards["content_engine"].lens
    assert "把尚不存在的客户投稿或团队日常当成现有素材" in cards["content_engine"].counterexamples
    assert "没有基线时先采集范围，不编造行业阈值" in cards["experiment_design"].lens
    assert "给任意数字贴上待验证标签" in cards["experiment_design"].counterexamples
    assert "新增产品、价格或优惠只能作为待验证方案，不能伪装成现有供给" in cards["monetization"].lens


def test_case_memory_is_project_local_and_returns_counterevidence_separately() -> None:
    memory = CaseMemory(
        (
            _case(
                case_id="support",
                project_id="project-a",
                supports=("真实转型过程适合建立信任",),
            ),
            _case(
                case_id="counter",
                project_id="project-a",
                status=CaseStatus.CONTESTED,
                contradicts=("真实转型过程适合建立信任",),
            ),
            _case(
                case_id="other-project",
                project_id="project-b",
                supports=("真实转型过程适合建立信任",),
            ),
            _case(
                case_id="retired",
                project_id="project-a",
                status=CaseStatus.RETIRED,
                supports=("真实转型过程适合建立信任",),
            ),
        )
    )

    recalled = memory.recall(
        CaseQuery(
            owner_id="owner-a",
            project_id="project-a",
            subject_kind=SubjectKind.PERSON,
            tags=("宝妈", "口播"),
            target_claims=("真实转型过程适合建立信任",),
        ),
        support_limit=3,
        counter_limit=3,
    )

    assert [case.case_episode_id for case in recalled.supporting] == ["support"]
    assert [case.case_episode_id for case in recalled.counterexamples] == ["counter"]
    assert all(case.project_id == "project-a" for case in (*recalled.supporting, *recalled.counterexamples))


def test_all_five_candidates_share_a_budget_but_receive_different_context() -> None:
    support_case = _case(
        case_id="support",
        project_id="project-a",
        supports=("职业事实比泛育儿标签更能形成差异",),
    )
    assembler = ContextAssembler(
        method_library=default_method_library(),
        case_memory=CaseMemory((support_case,)),
        max_context_chars=4_000,
    )
    request = ContextRequest(
        prompt="一个做过十年会计的宝妈怎么起号和变现？",
        brief=IncubationBrief(
            brief_version_id="brief-v1",
            brief_id="brief-a",
            version=1,
            owner_id="owner-a",
            project_id="project-a",
            created_at=NOW,
            subject_kind=SubjectKind.PERSON,
            subject_summary="做过十年会计的宝妈",
            constraints=("不展示孩子",),
            goals=("获得第一批财务咨询客户",),
        ),
        truths=(
            ProjectTruth(
                truth_id="truth-a",
                owner_id="owner-a",
                project_id="project-a",
                kind=TruthKind.USER_FACT,
                statement="有十年企业会计经验",
                created_at=NOW,
            ),
        ),
        method_query="定位 表现形式 变现",
        case_query=CaseQuery(
            owner_id="owner-a",
            project_id="project-a",
            subject_kind=SubjectKind.PERSON,
            tags=("宝妈", "知识服务"),
        ),
    )

    bundles = {variant: assembler.assemble(variant=variant, request=request) for variant in ArchitectureVariant}

    assert {variant.value for variant in bundles} == {
        "v4_fixed_workflow",
        "long_prompt_full_handbook",
        "thin_prompt_on_demand_methods",
        "thin_prompt_methods_truth",
        "thin_prompt_methods_truth_cases",
    }
    assert all(bundle.context_budget_chars == 4_000 for bundle in bundles.values())
    assert all(bundle.estimated_chars <= bundle.context_budget_chars for bundle in bundles.values())
    assert bundles[ArchitectureVariant.V4_FIXED_WORKFLOW].fixed_workflow is not None
    assert bundles[ArchitectureVariant.THIN_PROMPT_ON_DEMAND_METHODS].truths == ()
    assert bundles[ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH].truths
    assert bundles[ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH].cases == ()
    assert bundles[ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH_CASES].cases
    assert "固定阶段" not in bundles[ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH_CASES].constitution
