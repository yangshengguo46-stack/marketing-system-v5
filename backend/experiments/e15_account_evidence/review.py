from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from .contracts import (
    AccountEvidencePack,
    EvidenceRef,
    ReviewDisposition,
    SemanticSignal,
    SignalReviewDecision,
    StrictModel,
    TrainingRights,
    canonical_sha256,
)

REVIEW_QUEUE_CONTRACT_VERSION = "e15-signal-review-queue-v1"


class ReviewQueueDisposition(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    CONTESTED = "contested"


class ReviewQueueItem(StrictModel):
    signal_id: str = Field(min_length=1, max_length=160)
    post_id: str = Field(min_length=1, max_length=160)
    disposition: ReviewQueueDisposition = ReviewQueueDisposition.PENDING
    reason: str | None = Field(default=None, min_length=1, max_length=1_200)
    reviewer_ref: str | None = Field(default=None, min_length=1, max_length=500)
    reviewed_at: datetime | None = None
    corrected_signal: SemanticSignal | None = None

    @model_validator(mode="after")
    def validate_review_state(self) -> ReviewQueueItem:
        if self.disposition is ReviewQueueDisposition.PENDING:
            if any(
                value is not None
                for value in (
                    self.reason,
                    self.reviewer_ref,
                    self.reviewed_at,
                    self.corrected_signal,
                )
            ):
                raise ValueError("pending review cannot carry a decision")
            return self
        if not self.reason:
            raise ValueError("final review requires a reason")
        if not self.reviewer_ref or self.reviewed_at is None:
            raise ValueError("final review requires reviewer and reviewed_at")
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if self.disposition is ReviewQueueDisposition.CORRECTED:
            if self.corrected_signal is None or self.corrected_signal.signal_id != self.signal_id or self.corrected_signal.post_id != self.post_id:
                raise ValueError("corrected review requires a matching corrected_signal")
        elif self.corrected_signal is not None:
            raise ValueError("corrected_signal is allowed only for corrected review")
        return self


class SignalReviewQueue(StrictModel):
    contract_version: str = REVIEW_QUEUE_CONTRACT_VERSION
    pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: tuple[ReviewQueueItem, ...]

    @model_validator(mode="after")
    def validate_unique_items(self) -> SignalReviewQueue:
        ids = [item.signal_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("review queue signal ids must be unique")
        return self


class EvidenceReviewQueueItem(StrictModel):
    evidence_id: str = Field(min_length=1, max_length=160)
    post_id: str = Field(min_length=1, max_length=160)
    modality: str = Field(min_length=1, max_length=80)
    disposition: ReviewQueueDisposition = ReviewQueueDisposition.PENDING
    reason: str | None = Field(default=None, min_length=1, max_length=1_200)
    reviewer_ref: str | None = Field(default=None, min_length=1, max_length=500)
    reviewed_at: datetime | None = None
    corrected_evidence: EvidenceRef | None = None

    @model_validator(mode="after")
    def validate_review_state(self) -> EvidenceReviewQueueItem:
        if self.disposition is ReviewQueueDisposition.PENDING:
            if any(
                value is not None
                for value in (
                    self.reason,
                    self.reviewer_ref,
                    self.reviewed_at,
                    self.corrected_evidence,
                )
            ):
                raise ValueError("pending review cannot carry a decision")
            return self
        if not self.reason:
            raise ValueError("final review requires a reason")
        if not self.reviewer_ref or self.reviewed_at is None:
            raise ValueError("final review requires reviewer and reviewed_at")
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if self.disposition is ReviewQueueDisposition.CORRECTED:
            if self.corrected_evidence is None or self.corrected_evidence.evidence_id != self.evidence_id or self.corrected_evidence.post_id != self.post_id or self.corrected_evidence.modality != self.modality:
                raise ValueError("corrected review requires a matching corrected_evidence")
        elif self.corrected_evidence is not None:
            raise ValueError("corrected_evidence is allowed only for corrected review")
        return self


class EvidenceReviewQueue(StrictModel):
    contract_version: str = "e15-evidence-review-queue-v1"
    pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: tuple[EvidenceReviewQueueItem, ...]

    @model_validator(mode="after")
    def validate_unique_items(self) -> EvidenceReviewQueue:
        ids = [item.evidence_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("evidence review queue ids must be unique")
        return self


class ExtractionTrainingCandidate(StrictModel):
    pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights: TrainingRights
    reviewed_evidence: tuple[EvidenceRef, ...]
    evidence_decisions: tuple[EvidenceReviewQueueItem, ...]
    reviewed_signals: tuple[SemanticSignal, ...]
    signal_decisions: tuple[ReviewQueueItem, ...]


def _pack_sha256(pack: AccountEvidencePack) -> str:
    return canonical_sha256(pack.model_dump(mode="json"))


def build_signal_review_queue(pack: AccountEvidencePack) -> SignalReviewQueue:
    return SignalReviewQueue(
        pack_sha256=_pack_sha256(pack),
        items=tuple(ReviewQueueItem(signal_id=signal.signal_id, post_id=record.post_id) for record in pack.videos for signal in record.signals),
    )


def build_evidence_review_queue(pack: AccountEvidencePack) -> EvidenceReviewQueue:
    return EvidenceReviewQueue(
        pack_sha256=_pack_sha256(pack),
        items=tuple(
            EvidenceReviewQueueItem(
                evidence_id=evidence.evidence_id,
                post_id=record.post_id,
                modality=evidence.modality,
            )
            for record in pack.videos
            for evidence in record.media.evidence
            if evidence.modality != "video_frame"
        ),
    )


def build_training_candidate_from_queues(
    *,
    pack: AccountEvidencePack,
    signal_queue: SignalReviewQueue,
    evidence_queue: EvidenceReviewQueue,
    rights: TrainingRights,
) -> ExtractionTrainingCandidate:
    pack_sha256 = _pack_sha256(pack)
    if signal_queue.pack_sha256 != pack_sha256:
        raise ValueError("review queue does not match evidence pack")
    if evidence_queue.pack_sha256 != pack_sha256:
        raise ValueError("evidence review queue does not match evidence pack")
    if rights.source_rights is not pack.source_rights or rights.license_ref != pack.rights_ref:
        raise ValueError("training source rights do not match evidence pack")
    if any(item.disposition is ReviewQueueDisposition.PENDING for item in (*signal_queue.items, *evidence_queue.items)):
        raise ValueError("training candidate cannot contain pending review")
    if not rights.allow_model_training:
        raise ValueError("training candidate requires explicit model-training permission")

    disposition_map = {
        ReviewQueueDisposition.ACCEPTED: ReviewDisposition.ACCEPTED,
        ReviewQueueDisposition.CORRECTED: ReviewDisposition.CORRECTED,
        ReviewQueueDisposition.REJECTED: ReviewDisposition.REJECTED,
        ReviewQueueDisposition.CONTESTED: ReviewDisposition.CONTESTED,
    }
    decisions = tuple(
        SignalReviewDecision(
            target_signal_id=item.signal_id,
            disposition=disposition_map[item.disposition],
            reason=item.reason or "",
            corrected_signal=item.corrected_signal,
        )
        for item in signal_queue.items
    )
    signals = tuple(signal for video in pack.videos for signal in video.signals)
    signals_by_id = {signal.signal_id: signal for signal in signals}
    decisions_by_id = {decision.target_signal_id: decision for decision in decisions}
    if set(decisions_by_id) != set(signals_by_id):
        raise ValueError("every semantic signal requires exactly one review decision")

    reviewed_signals: list[SemanticSignal] = []
    for signal in signals:
        decision = decisions_by_id[signal.signal_id]
        if decision.disposition is ReviewDisposition.ACCEPTED:
            reviewed_signals.append(signal)
        elif decision.disposition is ReviewDisposition.CORRECTED:
            assert decision.corrected_signal is not None
            reviewed_signals.append(decision.corrected_signal)

    frame_evidence = tuple(evidence for video in pack.videos for evidence in video.media.evidence if evidence.modality == "video_frame")
    machine_evidence = tuple(evidence for video in pack.videos for evidence in video.media.evidence if evidence.modality != "video_frame")
    evidence_by_id = {evidence.evidence_id: evidence for evidence in machine_evidence}
    evidence_decisions_by_id = {decision.evidence_id: decision for decision in evidence_queue.items}
    if set(evidence_decisions_by_id) != set(evidence_by_id):
        raise ValueError("every machine evidence atom requires exactly one review decision")

    reviewed_evidence: list[EvidenceRef] = list(frame_evidence)
    for evidence in machine_evidence:
        decision = evidence_decisions_by_id[evidence.evidence_id]
        if decision.disposition is ReviewQueueDisposition.ACCEPTED:
            reviewed_evidence.append(evidence)
        elif decision.disposition is ReviewQueueDisposition.CORRECTED:
            assert decision.corrected_evidence is not None
            reviewed_evidence.append(decision.corrected_evidence)

    rejected_or_contested_evidence = {item.evidence_id for item in evidence_queue.items if item.disposition in {ReviewQueueDisposition.REJECTED, ReviewQueueDisposition.CONTESTED}}
    known_reviewed_evidence = {evidence.evidence_id for evidence in reviewed_evidence}
    for signal in reviewed_signals:
        if rejected_or_contested_evidence.intersection(signal.evidence_refs):
            raise ValueError("reviewed signal still cites rejected or contested evidence")
        if not set(signal.evidence_refs).issubset(known_reviewed_evidence):
            raise ValueError("reviewed signal cites unknown evidence")

    return ExtractionTrainingCandidate(
        pack_sha256=pack_sha256,
        rights=rights,
        reviewed_evidence=tuple(reviewed_evidence),
        evidence_decisions=evidence_queue.items,
        reviewed_signals=tuple(reviewed_signals),
        signal_decisions=signal_queue.items,
    )


__all__ = [
    "REVIEW_QUEUE_CONTRACT_VERSION",
    "EvidenceReviewQueue",
    "EvidenceReviewQueueItem",
    "ExtractionTrainingCandidate",
    "ReviewQueueDisposition",
    "ReviewQueueItem",
    "SignalReviewQueue",
    "build_evidence_review_queue",
    "build_signal_review_queue",
    "build_training_candidate_from_queues",
]
