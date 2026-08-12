from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from experiments.e15_account_evidence.aggregation import aggregate_account_records
from experiments.e15_account_evidence.contracts import (
    AccountEvidencePack,
    EpistemicStatus,
    EvidenceRef,
    ExtractorReceipt,
    MediaObservation,
    SemanticSignal,
    SignalDimension,
    SourceRights,
    TrainingRights,
    VideoEvidenceRecord,
)

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _evidence(post_id: str, suffix: str = "scene-1") -> EvidenceRef:
    return EvidenceRef(
        evidence_id=f"{post_id}-{suffix}",
        post_id=post_id,
        modality="scene",
        start_seconds=0,
        end_seconds=2.5,
        summary="画面中两个人物面对面交流。",
        artifact_ref=f"artifact://{post_id}/{suffix}",
        content_sha256=SHA_A,
    )


def _signal(
    post_id: str,
    *,
    signal_id: str | None = None,
    dimension: SignalDimension = SignalDimension.PRESENTATION_FORMAT,
    label: str = "situational-drama",
    status: EpistemicStatus = EpistemicStatus.OBSERVED,
    evidence_refs: tuple[str, ...] | None = None,
    alternatives: tuple[str, ...] = (),
) -> SemanticSignal:
    return SemanticSignal(
        signal_id=signal_id or f"{post_id}-{label}",
        post_id=post_id,
        dimension=dimension,
        label=label,
        statement="这条作品采用人物情境表演承载内容。",
        epistemic_status=status,
        evidence_refs=evidence_refs if evidence_refs is not None else (f"{post_id}-scene-1",),
        confidence=0.85 if status is not EpistemicStatus.UNKNOWN else None,
        alternative_explanations=alternatives,
        unknown_question="缺少可判断材料。" if status is EpistemicStatus.UNKNOWN else None,
    )


def _record(post_id: str, *, signals: tuple[SemanticSignal, ...] | None = None) -> VideoEvidenceRecord:
    evidence = _evidence(post_id)
    selected_signals = signals or (_signal(post_id),)
    return VideoEvidenceRecord(
        account_ref="account://demo/one",
        post_id=post_id,
        source_rights=SourceRights.USER_OWNED,
        rights_ref="rights://demo/user-owned",
        captured_at=NOW,
        media=MediaObservation(
            post_id=post_id,
            source_sha256=SHA_B,
            duration_seconds=8,
            evidence=(evidence,),
            limitations=("没有取得语音转写。",),
        ),
        signals=selected_signals,
        extractor_receipt=ExtractorReceipt(
            extractor_name="e15-bounded-semantic-extractor",
            model_name="fixture-model",
            prompt_sha256=SHA_A,
            schema_sha256=SHA_B,
            input_sha256=SHA_C,
            output_sha256=SHA_A,
            generated_at=NOW,
        ),
    )


def test_observed_signal_requires_traceable_evidence() -> None:
    with pytest.raises(ValidationError, match="observed signal requires evidence_refs"):
        _signal("post-1", evidence_refs=())


def test_inference_requires_an_alternative_explanation() -> None:
    with pytest.raises(ValidationError, match="inferred signal requires alternative_explanations"):
        _signal(
            "post-1",
            status=EpistemicStatus.INFERRED,
            dimension=SignalDimension.OPENING_FUNCTION,
            label="create-relation-tension",
        )


def test_unknown_signal_is_not_disguised_as_a_confident_claim() -> None:
    signal = _signal(
        "post-1",
        status=EpistemicStatus.UNKNOWN,
        dimension=SignalDimension.CALL_TO_ACTION,
        label="cta-unknown",
        evidence_refs=(),
    )

    assert signal.confidence is None
    assert signal.unknown_question == "缺少可判断材料。"


def test_video_record_rejects_forged_evidence_reference() -> None:
    forged = _signal("post-1", evidence_refs=("post-1-not-produced",))

    with pytest.raises(ValidationError, match="unknown evidence_refs"):
        _record("post-1", signals=(forged,))


def test_deterministic_aggregation_keeps_support_and_missing_sample_separate() -> None:
    first = _record("post-1")
    second = _record("post-2")
    third = _record(
        "post-3",
        signals=(
            _signal(
                "post-3",
                dimension=SignalDimension.PRESENTATION_FORMAT,
                label="talking-head",
            ),
        ),
    )

    pack = aggregate_account_records((first, second, third))
    repeated = next(item for item in pack.aggregates if item.label == "situational-drama")

    assert repeated.supporting_post_ids == ("post-1", "post-2")
    assert repeated.sample_post_ids_without_exact_match == ("post-3",)
    assert repeated.support_count == 2
    assert repeated.sample_size == 3
    assert repeated.sample_support_ratio == pytest.approx(2 / 3)
    assert repeated.support_status == "repeated_support"
    assert repeated.match_basis == "exact_dimension_label_and_status"
    assert repeated.epistemic_status is EpistemicStatus.OBSERVED
    assert not hasattr(repeated, "causal_performance_claim")
    assert not hasattr(repeated, "account_verdict")


def test_aggregation_does_not_turn_unknowns_into_account_patterns() -> None:
    unknown = _signal(
        "post-1",
        status=EpistemicStatus.UNKNOWN,
        dimension=SignalDimension.CALL_TO_ACTION,
        label="cta-not-identifiable",
        evidence_refs=(),
    )

    pack = aggregate_account_records((_record("post-1", signals=(unknown,)),))

    assert pack.aggregates == ()
    assert pack.videos[0].signals == (unknown,)


def test_aggregation_keeps_inference_status_visible() -> None:
    inferred = _signal(
        "post-1",
        status=EpistemicStatus.INFERRED,
        dimension=SignalDimension.CONTENT_PREMISE,
        label="possible-proposal-conflict",
        alternatives=("也可能是争执后的和解。",),
    )

    pack = aggregate_account_records((_record("post-1", signals=(inferred,)),))

    assert pack.aggregates[0].epistemic_status is EpistemicStatus.INFERRED


def test_single_video_pack_states_that_account_repetition_is_not_established() -> None:
    pack = aggregate_account_records((_record("post-1"),))

    assert any("Only one video" in limitation for limitation in pack.limitations)
    assert any("exact dimension" in limitation for limitation in pack.limitations)


def test_account_pack_rejects_cross_account_records() -> None:
    first = _record("post-1")
    second = _record("post-2").model_copy(update={"account_ref": "account://other"})

    with pytest.raises(ValueError, match="same account_ref"):
        aggregate_account_records((first, second))


def test_contract_has_no_verdict_virality_or_true_audience_fields() -> None:
    schema_text = json.dumps(AccountEvidencePack.model_json_schema(), sort_keys=True)

    for forbidden in (
        "account_verdict",
        "virality_cause",
        "true_audience_profile",
        "next_stage",
        "success_formula",
    ):
        assert forbidden not in schema_text


def test_analysis_only_material_can_never_become_training_data() -> None:
    with pytest.raises(ValidationError, match="analysis-only material cannot authorize model training"):
        TrainingRights(
            source_rights=SourceRights.ANALYSIS_ONLY,
            allow_model_training=True,
            license_ref="rights://public-observation-only",
        )
