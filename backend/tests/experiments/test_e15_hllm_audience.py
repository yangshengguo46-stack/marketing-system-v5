from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from experiments.e15_account_evidence.account_audience import AccountAudienceEvidencePack
from experiments.e15_account_evidence.audience_evidence import (
    AudienceAggregateSlice,
    AudienceAggregateSnapshot,
    AudienceBehaviorAction,
    AudienceBehaviorEvent,
    AudienceBehaviorSequence,
    AudienceEvidenceBasis,
    AudienceInteractionKind,
    AudienceInteractionObservation,
    AudienceProfileScope,
    AudienceSignalStatus,
    build_audience_behavior_sequences,
    pseudonymous_actor_ref,
)
from experiments.e15_account_evidence.hllm_audience import (
    HLLM_CREATOR_FIELDS,
    HLLM_UPSTREAM_COMMIT,
    HLLMAudienceAdapter,
    HLLMInferenceReceipt,
    HLLMProfileInference,
    hllm_profile_output_sha256,
)

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
SOURCE_SHA = "a" * 64


def _event(index: int, *, actor_ref: str, account_id: str = "watch-account") -> AudienceBehaviorEvent:
    return AudienceBehaviorEvent(
        event_id=f"comment-{index}",
        platform="douyin",
        account_id=account_id,
        actor_ref=actor_ref,
        action="comment",
        item_id=f"post-{index}",
        item_text=f"第 {index} 条腕表内容",
        interaction_text=f"评论者关心第 {index} 个问题",
        occurred_at=NOW + timedelta(minutes=index),
        captured_at=NOW + timedelta(hours=2),
        evidence_ref=f"comment://douyin/{index}",
    )


def _sequence(
    *,
    basis: AudienceEvidenceBasis = AudienceEvidenceBasis.AUDIENCE_INTERACTION_SEQUENCE,
    count: int = 3,
) -> AudienceBehaviorSequence:
    actor_ref = pseudonymous_actor_ref(
        platform="douyin",
        raw_actor_id="platform-user-123",
        local_salt="account-local-secret",
    )
    return AudienceBehaviorSequence(
        sequence_id="audience-sequence-1",
        platform="douyin",
        account_id="watch-account",
        actor_ref=actor_ref,
        basis=basis,
        events=tuple(_event(index, actor_ref=actor_ref) for index in range(count, 0, -1)),
        source_snapshot_sha256=SOURCE_SHA,
        sample_basis="该评论者在样本作品下可观察到的互动",
        limitations=("仅代表可见评论行为，不代表全部粉丝。",),
    )


def test_actor_reference_is_stable_pseudonym_and_does_not_expose_platform_id() -> None:
    first = pseudonymous_actor_ref(
        platform="douyin",
        raw_actor_id="platform-user-123",
        local_salt="account-local-secret",
    )
    second = pseudonymous_actor_ref(
        platform="douyin",
        raw_actor_id="platform-user-123",
        local_salt="account-local-secret",
    )

    assert first == second
    assert first.startswith("actor://sha256/")
    assert "platform-user-123" not in first


def test_behavior_sequence_rejects_cross_actor_and_cross_account_events() -> None:
    sequence = _sequence()
    wrong_actor = _event(4, actor_ref="actor://sha256/" + "b" * 64)
    wrong_account = _event(5, actor_ref=sequence.actor_ref, account_id="another-account")

    with pytest.raises(ValidationError, match="actor"):
        sequence.model_copy(update={"events": (*sequence.events, wrong_actor)}).__class__.model_validate(sequence.model_copy(update={"events": (*sequence.events, wrong_actor)}).model_dump())
    with pytest.raises(ValidationError, match="account"):
        AudienceBehaviorSequence.model_validate(sequence.model_copy(update={"events": (*sequence.events, wrong_account)}).model_dump())


def test_hllm_adapter_uses_chronological_audience_behavior_not_creator_post_history() -> None:
    row = HLLMAudienceAdapter(max_history=50).build_creator_row(
        sequence=_sequence(),
        target_title="腕表内容候选",
        target_description="用于检验受众兴趣匹配，不代表最终营销判断。",
    )

    assert tuple(row) == HLLM_CREATOR_FIELDS
    assert len(row["item_id_list"]) == 3
    assert all(isinstance(item_id, int) and item_id > 0 for item_id in row["item_id_list"])
    assert "第 1 条腕表内容" in row["title_list"][0]
    assert "第 3 条腕表内容" in row["title_list"][-1]
    assert "评论者关心第 1 个问题" in row["title_list"][0]
    assert row["user_profile"] == "{}"


def test_hllm_adapter_keeps_only_latest_fifty_events() -> None:
    row = HLLMAudienceAdapter(max_history=50).build_creator_row(
        sequence=_sequence(count=55),
        target_title="候选",
        target_description="说明",
    )

    assert len(row["title_list"]) == 50
    assert "第 6 条腕表内容" in row["title_list"][0]
    assert "第 55 条腕表内容" in row["title_list"][-1]


def test_account_performance_proxy_cannot_be_labeled_as_hllm_audience_sequence() -> None:
    with pytest.raises(ValueError, match="audience behavior sequence"):
        HLLMAudienceAdapter().build_creator_row(
            sequence=_sequence(basis=AudienceEvidenceBasis.ACCOUNT_CONTENT_PERFORMANCE_PROXY),
            target_title="候选",
            target_description="说明",
        )


def test_platform_aggregate_analytics_remain_observed_and_separate_from_hllm() -> None:
    snapshot = AudienceAggregateSnapshot(
        platform="douyin",
        account_id="watch-account",
        basis=AudienceEvidenceBasis.PLATFORM_AGGREGATE_ANALYTICS,
        status=AudienceSignalStatus.OBSERVED,
        slices=(
            AudienceAggregateSlice(
                dimension="age_band",
                label="25-34",
                value=0.42,
                value_kind="ratio",
                evidence_ref="dashboard://douyin/audience/age",
            ),
        ),
        captured_at=NOW,
        source_snapshot_sha256=SOURCE_SHA,
        limitations=("平台聚合口径以采集时页面为准。",),
    )

    assert snapshot.status is AudienceSignalStatus.OBSERVED
    assert snapshot.profile_scope is AudienceProfileScope.PLATFORM_OBSERVED_AUDIENCE

    with pytest.raises(ValidationError, match="platform aggregate"):
        AudienceAggregateSnapshot.model_validate(snapshot.model_copy(update={"status": AudienceSignalStatus.INFERRED}).model_dump())


def test_hllm_profile_requires_real_hllm_receipt_and_matching_input() -> None:
    adapter = HLLMAudienceAdapter()
    request = adapter.build_inference_request(sequence=_sequence())
    profile_values = {
        "inference_id": "profile-1",
        "platform": request.platform,
        "account_id": request.account_id,
        "sequence_id": request.sequence_id,
        "input_sha256": request.input_sha256,
        "profile_scope": AudienceProfileScope.INFERRED_AUDIENCE_COHORT,
        "status": AudienceSignalStatus.INFERRED,
        "basis": request.basis,
        "long_term_interests": ("机械结构与品牌历史",),
        "short_term_interests": ("入门腕表选择",),
        "needs": ("降低选表信息差",),
        "content_affinities": ("实物对比", "历史故事"),
        "supporting_evidence_refs": request.supporting_evidence_refs,
        "alternatives": ("评论行为也可能来自短期购买任务，而非长期兴趣。",),
        "limitations": request.limitations,
        "cluster_ref": None,
    }
    receipt = HLLMInferenceReceipt(
        model_family="bytedance_hllm_creator",
        upstream_commit=HLLM_UPSTREAM_COMMIT,
        checkpoint_id="hllm-creator-eval-checkpoint",
        checkpoint_sha256="b" * 64,
        adapter_version="e15-hllm-audience-v1",
        input_sha256=request.input_sha256,
        output_sha256=hllm_profile_output_sha256(profile_values),
        generated_at=NOW,
    )
    profile = HLLMProfileInference(
        **profile_values,
        receipt=receipt,
    )

    assert profile.receipt.input_sha256 == request.input_sha256
    assert profile.status is AudienceSignalStatus.INFERRED

    with pytest.raises(ValidationError, match="input hash"):
        HLLMProfileInference.model_validate(profile.model_copy(update={"receipt": receipt.model_copy(update={"input_sha256": "d" * 64})}).model_dump())

    with pytest.raises(ValidationError, match="output hash"):
        HLLMProfileInference.model_validate(profile.model_copy(update={"long_term_interests": ("被未授权中间层改写",)}).model_dump())


def test_generic_llm_cannot_impersonate_hllm_receipt() -> None:
    with pytest.raises(ValidationError, match="bytedance_hllm_creator"):
        HLLMInferenceReceipt(
            model_family="generic_chat_model",
            upstream_commit=HLLM_UPSTREAM_COMMIT,
            checkpoint_id="glm",
            checkpoint_sha256="b" * 64,
            adapter_version="e15-hllm-audience-v1",
            input_sha256="a" * 64,
            output_sha256="c" * 64,
            generated_at=NOW,
        )


def test_audience_interactions_group_into_cross_item_actor_sequences() -> None:
    interactions = (
        AudienceInteractionObservation.from_raw_actor(
            interaction_id="comment-2",
            platform="douyin",
            account_id="watch-account",
            item_id="post-2",
            item_text="腕表品牌历史",
            kind=AudienceInteractionKind.COMMENT,
            raw_actor_id="viewer-a",
            local_salt="account-local-secret",
            text="这个品牌最早是怎么来的？",
            occurred_at=NOW + timedelta(minutes=2),
            captured_at=NOW + timedelta(hours=1),
            evidence_ref="comment://douyin/comment-2",
        ),
        AudienceInteractionObservation.from_raw_actor(
            interaction_id="comment-1",
            platform="douyin",
            account_id="watch-account",
            item_id="post-1",
            item_text="机械表与石英表",
            kind=AudienceInteractionKind.COMMENT,
            raw_actor_id="viewer-a",
            local_salt="account-local-secret",
            text="日常通勤哪个更省心？",
            occurred_at=NOW + timedelta(minutes=1),
            captured_at=NOW + timedelta(hours=1),
            evidence_ref="comment://douyin/comment-1",
        ),
        AudienceInteractionObservation.from_raw_actor(
            interaction_id="comment-3",
            platform="douyin",
            account_id="watch-account",
            item_id="post-2",
            item_text="腕表品牌历史",
            kind=AudienceInteractionKind.COMMENT,
            raw_actor_id="viewer-b",
            local_salt="account-local-secret",
            text="想看更多历史故事。",
            occurred_at=NOW + timedelta(minutes=3),
            captured_at=NOW + timedelta(hours=1),
            evidence_ref="comment://douyin/comment-3",
        ),
    )

    sequences = build_audience_behavior_sequences(
        interactions=interactions,
        source_snapshot_sha256=SOURCE_SHA,
    )

    assert [len(sequence.events) for sequence in sequences] == [2, 1]
    assert [event.event_id for event in sequences[0].events] == ["comment-1", "comment-2"]
    assert all("viewer-a" not in sequence.model_dump_json() for sequence in sequences)
    assert "short sequence" in sequences[1].limitations[-1]


def test_audience_sequence_builder_rejects_mixed_accounts_and_duplicate_interactions() -> None:
    base = AudienceInteractionObservation.from_raw_actor(
        interaction_id="comment-1",
        platform="douyin",
        account_id="watch-account",
        item_id="post-1",
        item_text="腕表内容",
        kind=AudienceInteractionKind.COMMENT,
        raw_actor_id="viewer-a",
        local_salt="account-local-secret",
        text="评论",
        occurred_at=NOW,
        captured_at=NOW + timedelta(hours=1),
        evidence_ref="comment://douyin/comment-1",
    )

    with pytest.raises(ValueError, match="one account"):
        build_audience_behavior_sequences(
            interactions=(base, base.model_copy(update={"account_id": "another-account"})),
            source_snapshot_sha256=SOURCE_SHA,
        )
    with pytest.raises(ValueError, match="interaction ids"):
        build_audience_behavior_sequences(
            interactions=(base, base),
            source_snapshot_sha256=SOURCE_SHA,
        )


def test_non_comment_audience_actions_keep_their_business_meaning() -> None:
    interaction = AudienceInteractionObservation.from_raw_actor(
        interaction_id="product-click-1",
        platform="douyin",
        account_id="watch-account",
        item_id="post-1",
        item_text="腕表内容",
        kind=AudienceInteractionKind.PRODUCT_CLICK,
        raw_actor_id="viewer-a",
        local_salt="account-local-secret",
        occurred_at=NOW,
        captured_at=NOW + timedelta(minutes=1),
        evidence_ref="interaction://douyin/product-click-1",
    )

    sequence = build_audience_behavior_sequences(
        interactions=(interaction,),
        source_snapshot_sha256=SOURCE_SHA,
    )[0]

    assert sequence.events[0].action is AudienceBehaviorAction.PRODUCT_CLICK


def test_account_audience_pack_keeps_observed_analytics_sequences_and_hllm_inference_separate() -> None:
    sequence = _sequence()
    request = HLLMAudienceAdapter().build_inference_request(sequence=sequence)
    profile_values = {
        "inference_id": "profile-1",
        "platform": "douyin",
        "account_id": "watch-account",
        "sequence_id": sequence.sequence_id,
        "input_sha256": request.input_sha256,
        "profile_scope": AudienceProfileScope.INFERRED_AUDIENCE_COHORT,
        "status": AudienceSignalStatus.INFERRED,
        "basis": sequence.basis,
        "long_term_interests": ("腕表历史",),
        "short_term_interests": (),
        "needs": (),
        "content_affinities": (),
        "supporting_evidence_refs": request.supporting_evidence_refs,
        "alternatives": ("也可能只是一次购买前的信息搜索。",),
        "limitations": sequence.limitations,
        "cluster_ref": None,
    }
    receipt = HLLMInferenceReceipt(
        model_family="bytedance_hllm_creator",
        upstream_commit=HLLM_UPSTREAM_COMMIT,
        checkpoint_id="checkpoint",
        checkpoint_sha256="b" * 64,
        adapter_version="e15-hllm-audience-v1",
        input_sha256=request.input_sha256,
        output_sha256=hllm_profile_output_sha256(profile_values),
        generated_at=NOW,
    )
    inferred = HLLMProfileInference(
        **profile_values,
        receipt=receipt,
    )
    observed = AudienceAggregateSnapshot(
        platform="douyin",
        account_id="watch-account",
        basis=AudienceEvidenceBasis.PLATFORM_AGGREGATE_ANALYTICS,
        status=AudienceSignalStatus.OBSERVED,
        slices=(
            AudienceAggregateSlice(
                dimension="region",
                label="重庆",
                value=0.2,
                value_kind="ratio",
                evidence_ref="dashboard://douyin/audience/region",
            ),
        ),
        captured_at=NOW,
        source_snapshot_sha256=SOURCE_SHA,
    )

    pack = AccountAudienceEvidencePack(
        platform="douyin",
        account_id="watch-account",
        source_snapshot_sha256=SOURCE_SHA,
        aggregate_snapshots=(observed,),
        behavior_sequences=(sequence,),
        hllm_profiles=(inferred,),
        generated_at=NOW,
        limitations=("评论者样本不等于全部粉丝。",),
    )

    assert pack.observed_aggregate_count == 1
    assert pack.behavior_sequence_count == 1
    assert pack.hllm_profile_count == 1

    missing_sequence_values = {
        **profile_values,
        "sequence_id": "missing-sequence",
    }
    missing_sequence = HLLMProfileInference(
        **missing_sequence_values,
        receipt=receipt.model_copy(update={"output_sha256": hllm_profile_output_sha256(missing_sequence_values)}),
    )
    with pytest.raises(ValidationError, match="unknown sequence"):
        AccountAudienceEvidencePack.model_validate(pack.model_copy(update={"hllm_profiles": (missing_sequence,)}).model_dump())
