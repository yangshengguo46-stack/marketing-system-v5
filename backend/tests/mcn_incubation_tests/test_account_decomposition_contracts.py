from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest
from mcn_incubation.account_decomposition import (
    AccountEvidenceBundle,
    AccountIdentityStatus,
    AccountPatternHypothesis,
    AccountSnapshot,
    MediaAtomGap,
    MediaAtomReceipt,
    MediaAtomSet,
    MediaExecutionMode,
    MetricObservation,
    PostObservation,
    SamplingFrame,
    SocialPlatform,
    TransferCandidate,
)

NOW = datetime(2026, 8, 11, 16, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)


def _snapshot(
    *,
    account_id: str | None = "account-a",
    status: AccountIdentityStatus = AccountIdentityStatus.CONFIRMED,
) -> AccountSnapshot:
    return AccountSnapshot(
        snapshot_id="snapshot-a",
        owner_id="owner-a",
        project_id="project-a",
        platform=SocialPlatform.DOUYIN,
        platform_account_id=account_id,
        canonical_profile_url="https://www.douyin.com/user/account-a",
        identity_status=status,
        captured_at=NOW,
        source_ref="browser-artifact://snapshot-a",
        content_hash="a" * 64,
        display_name="同名账号",
        identity_evidence_refs=("browser-artifact://snapshot-a",),
    )


def _frame(
    *post_ids: str,
    visible_post_count: int | None = None,
    missing_reasons: tuple[str, ...] = (),
) -> SamplingFrame:
    return SamplingFrame(
        frame_id="frame-a",
        owner_id="owner-a",
        project_id="project-a",
        snapshot_id="snapshot-a",
        captured_at=NOW,
        selection_basis=("当前页面可见作品",),
        inclusion_rules=("作品作者 ID 与主页账号 ID 一致",),
        exclusion_rules=("排除页脚推荐和其他作者作品",),
        visible_post_count=visible_post_count,
        attempted_post_count=len(post_ids),
        included_post_ids=post_ids,
        missing_reasons=missing_reasons,
    )


def _post(
    post_id: str = "post-a",
    *,
    author_account_id: str | None = "account-a",
    metrics: tuple[MetricObservation, ...] = (),
    missing_metrics: tuple[str, ...] = (),
) -> PostObservation:
    return PostObservation(
        post_observation_id=post_id,
        owner_id="owner-a",
        project_id="project-a",
        snapshot_id="snapshot-a",
        platform_post_id=f"platform-{post_id}",
        author_platform_account_id=author_account_id,
        canonical_post_url=f"https://www.douyin.com/video/{post_id}",
        captured_at=NOW,
        content_hash=("b" if post_id == "post-a" else "c") * 64,
        source_ref=f"browser-artifact://{post_id}",
        metrics=metrics,
        missing_metrics=missing_metrics,
    )


def _bundle(
    *,
    snapshot: AccountSnapshot | None = None,
    frame: SamplingFrame | None = None,
    posts: tuple[PostObservation, ...] | None = None,
    atom_sets: tuple[MediaAtomSet, ...] = (),
    patterns: tuple[AccountPatternHypothesis, ...] = (),
    transfers: tuple[TransferCandidate, ...] = (),
) -> AccountEvidenceBundle:
    return AccountEvidenceBundle(
        snapshot=snapshot or _snapshot(),
        sampling_frame=frame or _frame("post-a", visible_post_count=1),
        posts=posts or (_post(),),
        media_atom_sets=atom_sets,
        pattern_hypotheses=patterns,
        transfer_candidates=transfers,
    )


def test_partial_capture_preserves_unknown_coverage_and_missing_metrics() -> None:
    bundle = _bundle(
        snapshot=_snapshot(status=AccountIdentityStatus.PROVISIONAL),
        frame=_frame(
            "post-a",
            visible_post_count=None,
            missing_reasons=("登录在采集中失效，页面总量未知",),
        ),
        posts=(_post(missing_metrics=("play_count", "share_count")),),
    )

    assert bundle.sampling_frame.coverage_ratio is None
    assert bundle.posts[0].metrics == ()
    assert bundle.posts[0].missing_metrics == ("play_count", "share_count")
    assert {warning.code for warning in bundle.warnings} >= {
        "identity_not_confirmed",
        "coverage_unknown",
        "capture_gap",
        "missing_public_metrics",
    }


def test_same_name_different_platform_ids_cannot_be_merged() -> None:
    with pytest.raises(ValueError, match="author identity"):
        _bundle(posts=(_post(author_account_id="account-b"),))


def test_missing_account_identity_is_preserved_as_unknown_instead_of_blocking_capture() -> None:
    bundle = _bundle(
        snapshot=_snapshot(
            account_id=None,
            status=AccountIdentityStatus.PROVISIONAL,
        ),
        posts=(_post(author_account_id=None),),
    )

    assert bundle.snapshot.platform_account_id is None
    assert bundle.posts[0].author_platform_account_id is None
    assert {warning.code for warning in bundle.warnings} >= {
        "identity_not_confirmed",
        "author_identity_unverified",
    }

    with pytest.raises(ValueError, match="confirmed identity"):
        _snapshot(account_id=None, status=AccountIdentityStatus.CONFIRMED)


def test_sampling_accepts_one_observed_post_without_a_fixed_minimum() -> None:
    frame = _frame("post-a", visible_post_count=1)
    pattern = AccountPatternHypothesis(
        pattern_hypothesis_id="pattern-a",
        owner_id="owner-a",
        project_id="project-a",
        snapshot_id="snapshot-a",
        frame_id="frame-a",
        dimension="opening_function",
        statement="样本中的开场先提出一个经营损失情境",
        supporting_post_ids=("post-a",),
        evidence_refs=("browser-artifact://post-a",),
        limitations=("当前只有一条可见作品，不能推成账号稳定规律",),
    )

    bundle = _bundle(frame=frame, patterns=(pattern,))

    assert frame.coverage_ratio == 1.0
    assert "pattern_without_counterexample" in {warning.code for warning in bundle.warnings}


def test_metric_capture_times_remain_separate_and_surface_mismatch() -> None:
    post = _post(
        metrics=(
            MetricObservation(
                name="play_count",
                value=1200,
                captured_at=NOW,
                source_ref="browser-artifact://post-a@16h",
            ),
            MetricObservation(
                name="comment_count",
                value=20,
                captured_at=LATER,
                source_ref="browser-artifact://post-a@18h",
            ),
        )
    )

    bundle = _bundle(posts=(post,))

    assert {metric.captured_at for metric in post.metrics} == {NOW, LATER}
    assert "metric_capture_time_mismatch" in {warning.code for warning in bundle.warnings}


def test_cloud_media_atoms_require_explicit_consent_but_a_gap_remains_valid() -> None:
    receipt = MediaAtomReceipt(
        capability="asr-subtitles",
        execution_mode=MediaExecutionMode.CLOUD,
        tool_version="mediakit-cli 0.2.0",
        schema_hash="d" * 64,
        input_hash="b" * 64,
        output_hash="e" * 64,
        task_id="task-a",
        completed_at=NOW,
        artifact_refs=("artifact://post-a/asr.json",),
    )

    with pytest.raises(ValueError, match="cloud processing consent"):
        MediaAtomSet(
            atom_set_id="atoms-a",
            owner_id="owner-a",
            project_id="project-a",
            post_observation_id="post-a",
            created_at=NOW,
            input_hash="b" * 64,
            rights_basis=("用户仅授权查看公开作品",),
            cloud_processing_consent=False,
            receipts=(receipt,),
        )

    gap_only = MediaAtomSet(
        atom_set_id="atoms-a",
        owner_id="owner-a",
        project_id="project-a",
        post_observation_id="post-a",
        created_at=NOW,
        input_hash="b" * 64,
        rights_basis=("用户仅授权查看公开作品",),
        cloud_processing_consent=False,
        gaps=(MediaAtomGap(capability="asr-subtitles", reason="未获得云处理同意"),),
    )
    bundle = _bundle(atom_sets=(gap_only,))

    assert "media_atom_gap" in {warning.code for warning in bundle.warnings}


def test_media_modality_conflicts_are_preserved_instead_of_silently_resolved() -> None:
    atom_set = MediaAtomSet(
        atom_set_id="atoms-a",
        owner_id="owner-a",
        project_id="project-a",
        post_observation_id="post-a",
        created_at=NOW,
        input_hash="b" * 64,
        rights_basis=("用户授权本地分析",),
        cloud_processing_consent=False,
        conflicts=("ASR 与 OCR 对 00:03-00:05 的商品名记录不一致",),
    )

    bundle = _bundle(atom_sets=(atom_set,))

    assert bundle.media_atom_sets[0].conflicts
    assert "modality_conflict" in {warning.code for warning in bundle.warnings}


def test_pattern_support_and_counterexamples_must_belong_to_the_declared_sample() -> None:
    pattern = AccountPatternHypothesis(
        pattern_hypothesis_id="pattern-a",
        owner_id="owner-a",
        project_id="project-a",
        snapshot_id="snapshot-a",
        frame_id="frame-a",
        dimension="proof_function",
        statement="演示过程可能承担降低顾虑的功能",
        supporting_post_ids=("post-a",),
        counterexample_post_ids=("post-outside-frame",),
        evidence_refs=("browser-artifact://post-a",),
        limitations=("不能据此声称演示导致更高播放",),
    )

    with pytest.raises(ValueError, match="sampled posts"):
        _bundle(patterns=(pattern,))


def test_pattern_and_transfer_evidence_refs_must_exist_in_the_same_bundle() -> None:
    forged_pattern = AccountPatternHypothesis(
        pattern_hypothesis_id="pattern-a",
        owner_id="owner-a",
        project_id="project-a",
        snapshot_id="snapshot-a",
        frame_id="frame-a",
        dimension="proof_function",
        statement="演示过程可能承担降低顾虑的功能",
        supporting_post_ids=("post-a",),
        evidence_refs=("browser-artifact://not-in-this-bundle",),
    )
    with pytest.raises(ValueError, match="unknown evidence refs"):
        _bundle(patterns=(forged_pattern,))

    pattern = AccountPatternHypothesis(
        pattern_hypothesis_id="pattern-a",
        owner_id="owner-a",
        project_id="project-a",
        snapshot_id="snapshot-a",
        frame_id="frame-a",
        dimension="proof_function",
        statement="演示过程可能承担降低顾虑的功能",
        supporting_post_ids=("post-a",),
        evidence_refs=("browser-artifact://post-a",),
    )
    forged_transfer = TransferCandidate(
        transfer_candidate_id="transfer-a",
        owner_id="owner-a",
        project_id="project-a",
        source_snapshot_id="snapshot-a",
        pattern_hypothesis_ids=("pattern-a",),
        function_to_transfer="用过程演示降低对专业判断的不信任",
        required_conditions=("当前主体有权展示原创工作过程",),
        adaptation_notes=("重新设计适合当前主体的演示",),
        originality_boundaries=("不复制台词、镜头、音乐或人物标签",),
        evidence_refs=("artifact://forged-media-result",),
    )
    with pytest.raises(ValueError, match="unknown evidence refs"):
        _bundle(patterns=(pattern,), transfers=(forged_transfer,))

    valid_transfer = TransferCandidate(
        transfer_candidate_id="transfer-a",
        owner_id="owner-a",
        project_id="project-a",
        source_snapshot_id="snapshot-a",
        pattern_hypothesis_ids=("pattern-a",),
        function_to_transfer="用过程演示降低对专业判断的不信任",
        required_conditions=("当前主体有权展示原创工作过程",),
        adaptation_notes=("重新设计适合当前主体的演示",),
        originality_boundaries=("不复制台词、镜头、音乐或人物标签",),
        evidence_refs=("pattern-a",),
    )
    bundle = _bundle(patterns=(pattern,), transfers=(valid_transfer,))

    assert bundle.transfer_candidates == (valid_transfer,)


def test_transfer_candidate_carries_function_conditions_and_originality_boundary() -> None:
    with pytest.raises(ValueError, match="originality_boundaries"):
        TransferCandidate(
            transfer_candidate_id="transfer-a",
            owner_id="owner-a",
            project_id="project-a",
            source_snapshot_id="snapshot-a",
            pattern_hypothesis_ids=("pattern-a",),
            function_to_transfer="用经营损失情境让目标用户快速识别问题",
            required_conditions=("当前主体有真实可公开的问题情境",),
            adaptation_notes=("重新选择适合会计主体的原创案例",),
            originality_boundaries=(),
            evidence_refs=("browser-artifact://post-a",),
        )


def test_canonical_urls_reject_query_tokens_and_credentials() -> None:
    with pytest.raises(ValueError, match="canonical_profile_url"):
        AccountSnapshot(
            snapshot_id="snapshot-a",
            owner_id="owner-a",
            project_id="project-a",
            platform=SocialPlatform.XIAOHONGSHU,
            platform_account_id="account-a",
            canonical_profile_url="https://example.test/profile/account-a?xsec_token=secret",
            identity_status=AccountIdentityStatus.CONFIRMED,
            captured_at=NOW,
            source_ref="browser-artifact://snapshot-a",
            content_hash="a" * 64,
        )


def test_account_evidence_contract_has_no_verdict_score_or_fixed_stage_fields() -> None:
    model_types = (
        AccountSnapshot,
        SamplingFrame,
        PostObservation,
        MediaAtomSet,
        AccountPatternHypothesis,
        TransferCandidate,
        AccountEvidenceBundle,
    )
    names = {field.name for model_type in model_types for field in fields(model_type)}

    assert not {
        "account_score",
        "verdict",
        "next_stage",
        "required_sample_count",
        "universal_success_formula",
        "causal_performance_claim",
    }.intersection(names)
