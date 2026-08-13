from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from experiments.e15_account_evidence.aggregation import aggregate_account_records
from experiments.e15_account_evidence.contracts import (
    EpistemicStatus,
    EvidenceRef,
    ExtractorReceipt,
    MediaObservation,
    SemanticSignal,
    SignalDimension,
    SourceRights,
    VideoEvidenceRecord,
)
from experiments.e15_account_evidence.lead_projection import (
    LeadProjectionBudget,
    build_lead_account_projection,
    serialize_lead_account_projection,
)
from experiments.e15_account_evidence.source_snapshot import (
    AccountProfileObservation,
    AccountSourceSnapshot,
    CollectionMethod,
    PostListObservation,
)

NOW = datetime(2026, 8, 13, 8, 0, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _source_snapshot(post_count: int = 500) -> AccountSourceSnapshot:
    return AccountSourceSnapshot(
        profile=AccountProfileObservation(
            platform="douyin",
            account_id="public-account-1",
            canonical_url="https://www.douyin.com/user/public-account-1",
            display_name="示例账号",
            bio="一个很长但仍然只是公开资料的简介" * 80,
            visible_work_count=post_count,
            captured_at=NOW,
        ),
        posts=tuple(
            PostListObservation(
                post_id=f"post-{index:03d}",
                canonical_url=f"https://www.douyin.com/video/post-{index:03d}",
                caption=(f"第 {index} 条作品的公开标题 " * 30),
                captured_at=NOW,
                public_metrics={"likes": index},
            )
            for index in range(post_count)
        ),
        collection_method=CollectionMethod.VISIBLE_BROWSER_AUTHORIZED,
        source_rights=SourceRights.ANALYSIS_ONLY,
        rights_ref="request://user-supplied-link/2026-08-13",
        requested_url="https://v.douyin.com/example/",
        sample_basis="Bounded user-requested public sample.",
        captured_at=NOW,
        limitations=("Public profile observation does not establish causality.",),
    )


def _record(post_id: str, *, label: str, dimension: SignalDimension) -> VideoEvidenceRecord:
    evidence_id = f"{post_id}-asr-001"
    return VideoEvidenceRecord(
        account_ref="account://douyin/public-account-1",
        post_id=post_id,
        source_rights=SourceRights.ANALYSIS_ONLY,
        rights_ref="request://user-supplied-link/2026-08-13",
        captured_at=NOW,
        media=MediaObservation(
            post_id=post_id,
            source_sha256=SHA_A,
            duration_seconds=60,
            evidence=(
                EvidenceRef(
                    evidence_id=evidence_id,
                    post_id=post_id,
                    modality="asr",
                    start_seconds=0,
                    end_seconds=12,
                    summary="完整字幕" * 200,
                    artifact_ref=f"artifact://private-cache/{post_id}/full-transcript.json",
                    content_sha256=SHA_B,
                ),
            ),
            limitations=(),
        ),
        signals=(
            SemanticSignal(
                signal_id=f"{post_id}-{dimension.value}-{label}",
                post_id=post_id,
                dimension=dimension,
                label=label,
                statement=f"作品呈现了 {label} 的可复核候选模式。",
                epistemic_status=EpistemicStatus.INFERRED,
                evidence_refs=(evidence_id,),
                confidence=0.7,
                alternative_explanations=("也可能只是单条作品的题材变化。",),
            ),
        ),
        extractor_receipt=ExtractorReceipt(
            extractor_name="fixture",
            model_name="fixture-model",
            prompt_sha256=SHA_A,
            schema_sha256=SHA_B,
            input_sha256=SHA_C,
            output_sha256=SHA_A,
            generated_at=NOW,
        ),
    )


def _pack():
    dimensions = tuple(SignalDimension)
    records = tuple(
        _record(
            f"post-{index:03d}",
            label=f"pattern-{index % 24:02d}",
            dimension=dimensions[index % len(dimensions)],
        )
        for index in range(96)
    )
    return aggregate_account_records(records, generated_at=NOW)


def test_lead_projection_is_bounded_even_when_source_and_evidence_are_large() -> None:
    budget = LeadProjectionBudget(
        max_utf8_bytes=12_000,
        max_patterns=24,
        max_representative_posts=8,
        max_refs_per_pattern=3,
    )

    projection = build_lead_account_projection(
        source=_source_snapshot(),
        pack=_pack(),
        budget=budget,
    )
    encoded = serialize_lead_account_projection(projection)

    assert len(encoded.encode("utf-8")) <= budget.max_utf8_bytes
    assert len(projection.patterns) <= budget.max_patterns
    assert len(projection.representative_posts) <= budget.max_representative_posts
    assert projection.sampling.visible_work_count == 500
    assert projection.sampling.captured_post_count == 500
    assert projection.sampling.analyzed_post_count == 96


def test_lead_projection_excludes_raw_media_dom_and_private_artifacts() -> None:
    projection = build_lead_account_projection(
        source=_source_snapshot(),
        pack=_pack(),
        budget=LeadProjectionBudget(max_utf8_bytes=12_000),
    )
    encoded = serialize_lead_account_projection(projection)

    for forbidden in (
        "完整字幕",
        "full-transcript.json",
        "artifact://private-cache",
        "raw_html",
        "cookies",
        "local_storage",
        "/Users/",
        "data:image",
    ):
        assert forbidden not in encoded

    assert "evidence_ids" in encoded
    assert "untrusted observed data" in encoded


def test_projection_is_deterministic_and_references_detail_on_demand() -> None:
    source = _source_snapshot()
    pack = _pack()
    budget = LeadProjectionBudget(max_utf8_bytes=12_000)

    first = build_lead_account_projection(source=source, pack=pack, budget=budget)
    second = build_lead_account_projection(source=source, pack=pack, budget=budget)

    assert serialize_lead_account_projection(first) == serialize_lead_account_projection(second)
    assert first.detail_lookup == "Use a post_id or evidence_id to request one bounded local detail."
    assert json.loads(serialize_lead_account_projection(first))["contract_version"] == "e15-lead-account-projection-v1"
    assert "untrusted observed data" in first.epistemic_notice


def test_projection_rejects_cross_account_or_cross_rights_evidence() -> None:
    source = _source_snapshot()
    pack = _pack()

    with pytest.raises(ValueError, match="account_ref does not match"):
        build_lead_account_projection(
            source=source,
            pack=pack.model_copy(update={"account_ref": "account://douyin/other"}),
        )

    with pytest.raises(ValueError, match="source rights do not match"):
        build_lead_account_projection(
            source=source,
            pack=pack.model_copy(update={"rights_ref": "rights://another-request"}),
        )


def test_projection_rejects_analyzed_posts_missing_from_source_snapshot() -> None:
    source = _source_snapshot(post_count=10)

    with pytest.raises(ValueError, match="not present in the source snapshot"):
        build_lead_account_projection(source=source, pack=_pack())
