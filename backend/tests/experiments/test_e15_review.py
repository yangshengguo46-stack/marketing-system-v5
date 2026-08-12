from __future__ import annotations

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
    TrainingRights,
    VideoEvidenceRecord,
)
from experiments.e15_account_evidence.review import (
    EvidenceReviewQueue,
    EvidenceReviewQueueItem,
    ExtractionTrainingCandidate,
    ReviewQueueDisposition,
    ReviewQueueItem,
    SignalReviewQueue,
    build_evidence_review_queue,
    build_signal_review_queue,
    build_training_candidate_from_queues,
)

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def _pack(*, signal_evidence_refs: tuple[str, ...] | None = None):
    evidence = EvidenceRef(
        evidence_id="post-1-frame-001",
        post_id="post-1",
        modality="video_frame",
        start_seconds=1,
        end_seconds=1,
        summary="A person addresses the camera.",
        artifact_ref="artifact://e15/post-1/frames/frame-001.jpg",
        content_sha256="a" * 64,
    )
    asr = evidence.model_copy(
        update={
            "evidence_id": "post-1-asr-001",
            "modality": "asr",
            "start_seconds": 0.1,
            "end_seconds": 1.8,
            "summary": "ASR machine observation: hello world",
            "artifact_ref": "artifact://e15/post-1/mediakit/asr/001",
            "content_sha256": "e" * 64,
        }
    )
    ocr = evidence.model_copy(
        update={
            "evidence_id": "post-1-ocr-001",
            "modality": "ocr",
            "start_seconds": 3,
            "end_seconds": 3.2,
            "summary": "OCR machine observation: 5",
            "artifact_ref": "artifact://e15/post-1/mediakit/ocr/001",
            "content_sha256": "f" * 64,
        }
    )
    signal = SemanticSignal(
        signal_id="post-1-format-001",
        post_id="post-1",
        dimension=SignalDimension.PRESENTATION_FORMAT,
        label="talking-head",
        statement="The person addresses the camera directly.",
        epistemic_status=EpistemicStatus.OBSERVED,
        evidence_refs=signal_evidence_refs or (evidence.evidence_id,),
    )
    record = VideoEvidenceRecord(
        account_ref="account://demo/one",
        post_id="post-1",
        source_rights=SourceRights.USER_OWNED,
        rights_ref="rights://demo/user-owned",
        captured_at=NOW,
        media=MediaObservation(
            post_id="post-1",
            source_sha256="b" * 64,
            duration_seconds=8,
            evidence=(evidence, asr, ocr),
        ),
        signals=(signal,),
        extractor_receipt=ExtractorReceipt(
            extractor_name="fixture",
            model_name="fixture-model",
            prompt_sha256="a" * 64,
            schema_sha256="b" * 64,
            input_sha256="c" * 64,
            output_sha256="d" * 64,
            generated_at=NOW,
        ),
    )
    return aggregate_account_records((record,), generated_at=NOW)


def test_review_queue_starts_pending_and_is_bound_to_pack_hash() -> None:
    pack = _pack()

    queue = build_signal_review_queue(pack)

    assert queue.items[0].disposition is ReviewQueueDisposition.PENDING
    assert queue.items[0].signal_id == "post-1-format-001"
    assert len(queue.pack_sha256) == 64


def test_evidence_review_queue_includes_machine_atoms_but_not_sampled_frames() -> None:
    pack = _pack()

    queue = build_evidence_review_queue(pack)

    assert [item.evidence_id for item in queue.items] == [
        "post-1-asr-001",
        "post-1-ocr-001",
    ]
    assert {item.modality for item in queue.items} == {"asr", "ocr"}
    assert {item.disposition for item in queue.items} == {ReviewQueueDisposition.PENDING}


def test_pending_or_wrong_pack_queue_cannot_become_training_data() -> None:
    pack = _pack()
    queue = build_signal_review_queue(pack)
    rights = TrainingRights(
        source_rights=SourceRights.USER_OWNED,
        allow_model_training=True,
        license_ref="rights://demo/user-owned",
    )

    with pytest.raises(ValueError, match="pending review"):
        build_training_candidate_from_queues(
            pack=pack,
            signal_queue=queue,
            evidence_queue=build_evidence_review_queue(pack),
            rights=rights,
        )

    accepted = queue.model_copy(
        update={
            "pack_sha256": "f" * 64,
            "items": (
                ReviewQueueItem(
                    signal_id="post-1-format-001",
                    post_id="post-1",
                    disposition=ReviewQueueDisposition.ACCEPTED,
                    reason="Reviewed against the source frame.",
                    reviewer_ref="reviewer://fixture/operator",
                    reviewed_at=NOW,
                ),
            ),
        }
    )
    with pytest.raises(ValueError, match="does not match evidence pack"):
        build_training_candidate_from_queues(
            pack=pack,
            signal_queue=accepted,
            evidence_queue=build_evidence_review_queue(pack),
            rights=rights,
        )


def test_reviewed_queue_exports_only_accepted_or_corrected_labels() -> None:
    pack = _pack()
    queue = build_signal_review_queue(pack)
    accepted = SignalReviewQueue(
        pack_sha256=queue.pack_sha256,
        items=(
            ReviewQueueItem(
                signal_id="post-1-format-001",
                post_id="post-1",
                disposition=ReviewQueueDisposition.ACCEPTED,
                reason="Reviewed against the source frame.",
                reviewer_ref="reviewer://fixture/operator",
                reviewed_at=NOW,
            ),
        ),
    )
    rights = TrainingRights(
        source_rights=SourceRights.LICENSED,
        allow_model_training=True,
        license_ref="rights://demo/user-owned",
    )
    evidence_queue = EvidenceReviewQueue(
        pack_sha256=queue.pack_sha256,
        items=(
            EvidenceReviewQueueItem(
                evidence_id="post-1-asr-001",
                post_id="post-1",
                modality="asr",
                disposition=ReviewQueueDisposition.ACCEPTED,
                reason="Compared with source audio.",
                reviewer_ref="reviewer://fixture/operator",
                reviewed_at=NOW,
            ),
            EvidenceReviewQueueItem(
                evidence_id="post-1-ocr-001",
                post_id="post-1",
                modality="ocr",
                disposition=ReviewQueueDisposition.REJECTED,
                reason="The digit is not visible in the referenced frames.",
                reviewer_ref="reviewer://fixture/operator",
                reviewed_at=NOW,
            ),
        ),
    )

    with pytest.raises(ValueError, match="source rights do not match"):
        build_training_candidate_from_queues(
            pack=pack,
            signal_queue=accepted,
            evidence_queue=evidence_queue,
            rights=rights,
        )

    candidate = build_training_candidate_from_queues(
        pack=pack,
        signal_queue=accepted,
        evidence_queue=evidence_queue,
        rights=rights.model_copy(update={"source_rights": SourceRights.USER_OWNED}),
    )

    assert isinstance(candidate, ExtractionTrainingCandidate)
    assert candidate.reviewed_signals == pack.videos[0].signals
    assert [item.evidence_id for item in candidate.reviewed_evidence] == ["post-1-frame-001", "post-1-asr-001"]
    assert candidate.signal_decisions[0].reviewer_ref == "reviewer://fixture/operator"
    assert candidate.signal_decisions[0].reviewed_at == NOW
    assert not hasattr(candidate, "signal_corrections")
    assert candidate.evidence_decisions[1].disposition is ReviewQueueDisposition.REJECTED


def test_signal_citing_rejected_machine_evidence_must_be_corrected_or_rejected() -> None:
    pack = _pack(signal_evidence_refs=("post-1-frame-001", "post-1-ocr-001"))
    pack_hash = build_signal_review_queue(pack).pack_sha256
    signal_queue = SignalReviewQueue(
        pack_sha256=pack_hash,
        items=(
            ReviewQueueItem(
                signal_id="post-1-format-001",
                post_id="post-1",
                disposition=ReviewQueueDisposition.ACCEPTED,
                reason="The format label is otherwise correct.",
                reviewer_ref="reviewer://fixture/operator",
                reviewed_at=NOW,
            ),
        ),
    )
    evidence_queue = EvidenceReviewQueue(
        pack_sha256=pack_hash,
        items=(
            EvidenceReviewQueueItem(
                evidence_id="post-1-asr-001",
                post_id="post-1",
                modality="asr",
                disposition=ReviewQueueDisposition.ACCEPTED,
                reason="Compared with source audio.",
                reviewer_ref="reviewer://fixture/operator",
                reviewed_at=NOW,
            ),
            EvidenceReviewQueueItem(
                evidence_id="post-1-ocr-001",
                post_id="post-1",
                modality="ocr",
                disposition=ReviewQueueDisposition.REJECTED,
                reason="False positive.",
                reviewer_ref="reviewer://fixture/operator",
                reviewed_at=NOW,
            ),
        ),
    )
    rights = TrainingRights(
        source_rights=SourceRights.USER_OWNED,
        allow_model_training=True,
        license_ref="rights://demo/user-owned",
    )

    with pytest.raises(ValueError, match="rejected or contested evidence"):
        build_training_candidate_from_queues(
            pack=pack,
            signal_queue=signal_queue,
            evidence_queue=evidence_queue,
            rights=rights,
        )


def test_queue_requires_reason_and_matching_corrected_signal() -> None:
    pack = _pack()
    original = pack.videos[0].signals[0]

    with pytest.raises(ValueError, match="final review requires a reason"):
        ReviewQueueItem(
            signal_id=original.signal_id,
            post_id=original.post_id,
            disposition=ReviewQueueDisposition.REJECTED,
        )

    with pytest.raises(ValueError, match="matching corrected_signal"):
        ReviewQueueItem(
            signal_id=original.signal_id,
            post_id=original.post_id,
            disposition=ReviewQueueDisposition.CORRECTED,
            reason="The format label is too broad.",
            reviewer_ref="reviewer://fixture/operator",
            reviewed_at=NOW,
            corrected_signal=original.model_copy(update={"signal_id": "another-id"}),
        )

    with pytest.raises(ValueError, match="reviewer and reviewed_at"):
        ReviewQueueItem(
            signal_id=original.signal_id,
            post_id=original.post_id,
            disposition=ReviewQueueDisposition.ACCEPTED,
            reason="Reviewed but missing audit identity.",
        )


def test_corrected_evidence_must_keep_identity_and_modality() -> None:
    evidence = _pack().videos[0].media.evidence[1]

    with pytest.raises(ValueError, match="matching corrected_evidence"):
        EvidenceReviewQueueItem(
            evidence_id=evidence.evidence_id,
            post_id=evidence.post_id,
            modality=evidence.modality,
            disposition=ReviewQueueDisposition.CORRECTED,
            reason="ASR text needs correction.",
            reviewer_ref="reviewer://fixture/operator",
            reviewed_at=NOW,
            corrected_evidence=evidence.model_copy(update={"modality": "ocr"}),
        )


def test_corrected_signal_cannot_cite_unknown_evidence() -> None:
    pack = _pack()
    original = pack.videos[0].signals[0]
    pack_hash = build_signal_review_queue(pack).pack_sha256
    corrected = original.model_copy(update={"evidence_refs": ("post-1-frame-does-not-exist",)})
    signal_queue = SignalReviewQueue(
        pack_sha256=pack_hash,
        items=(
            ReviewQueueItem(
                signal_id=original.signal_id,
                post_id=original.post_id,
                disposition=ReviewQueueDisposition.CORRECTED,
                reason="Replace the signal with a narrower statement.",
                reviewer_ref="reviewer://fixture/operator",
                reviewed_at=NOW,
                corrected_signal=corrected,
            ),
        ),
    )
    evidence_queue = EvidenceReviewQueue(
        pack_sha256=pack_hash,
        items=tuple(
            item.model_copy(
                update={
                    "disposition": ReviewQueueDisposition.ACCEPTED,
                    "reason": "Reviewed against source media.",
                    "reviewer_ref": "reviewer://fixture/operator",
                    "reviewed_at": NOW,
                }
            )
            for item in build_evidence_review_queue(pack).items
        ),
    )
    rights = TrainingRights(
        source_rights=SourceRights.USER_OWNED,
        allow_model_training=True,
        license_ref="rights://demo/user-owned",
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        build_training_candidate_from_queues(
            pack=pack,
            signal_queue=signal_queue,
            evidence_queue=evidence_queue,
            rights=rights,
        )
