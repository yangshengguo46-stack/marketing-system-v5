from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EpistemicStatus(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class SignalDimension(StrEnum):
    CONTENT_SUBJECT = "content_subject"
    AUDIENCE_SITUATION = "audience_situation"
    CONTENT_PREMISE = "content_premise"
    TOPIC = "topic"
    PRESENTATION_FORMAT = "presentation_format"
    OPENING_FUNCTION = "opening_function"
    NARRATIVE_MECHANISM = "narrative_mechanism"
    PROOF_FUNCTION = "proof_function"
    COMMERCIAL_PRESENCE = "commercial_presence"
    CALL_TO_ACTION = "call_to_action"
    PRODUCTION_BURDEN = "production_burden"


class SourceRights(StrEnum):
    ANALYSIS_ONLY = "analysis_only"
    USER_OWNED = "user_owned"
    LICENSED = "licensed"
    PUBLIC_DOMAIN = "public_domain"


class ReviewDisposition(StrEnum):
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    CONTESTED = "contested"


class EvidenceRef(StrictModel):
    evidence_id: str = Field(min_length=1, max_length=160)
    post_id: str = Field(min_length=1, max_length=160)
    modality: str = Field(min_length=1, max_length=80)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    summary: str = Field(min_length=1, max_length=1_200)
    artifact_ref: str = Field(min_length=1, max_length=1_000)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_time_range(self) -> EvidenceRef:
        if self.end_seconds is not None and self.start_seconds is None:
            raise ValueError("end_seconds requires start_seconds")
        if self.start_seconds is not None and self.end_seconds is not None and self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds cannot precede start_seconds")
        return self


class SemanticSignal(StrictModel):
    signal_id: str = Field(min_length=1, max_length=160)
    post_id: str = Field(min_length=1, max_length=160)
    dimension: SignalDimension
    label: str = Field(min_length=1, max_length=160)
    statement: str = Field(min_length=1, max_length=1_200)
    epistemic_status: EpistemicStatus
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    confidence: float | None = Field(default=None, ge=0, le=1)
    alternative_explanations: tuple[str, ...] = Field(default_factory=tuple)
    unknown_question: str | None = Field(default=None, min_length=1, max_length=600)

    @field_validator("confidence")
    @classmethod
    def finite_confidence(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(value):
            raise ValueError("confidence must be finite")
        return value

    @model_validator(mode="after")
    def validate_epistemic_contract(self) -> SemanticSignal:
        if self.epistemic_status is EpistemicStatus.OBSERVED and not self.evidence_refs:
            raise ValueError("observed signal requires evidence_refs")
        if self.epistemic_status is EpistemicStatus.INFERRED:
            if not self.evidence_refs:
                raise ValueError("inferred signal requires evidence_refs")
            if not self.alternative_explanations:
                raise ValueError("inferred signal requires alternative_explanations")
        if self.epistemic_status is EpistemicStatus.UNKNOWN:
            if self.confidence is not None:
                raise ValueError("unknown signal cannot carry confidence")
            if not self.unknown_question:
                raise ValueError("unknown signal requires unknown_question")
        return self


class MediaKitReceipt(StrictModel):
    capability: str = Field(min_length=1, max_length=120)
    execution_mode: str = Field(pattern=r"^(local|cloud)$")
    tool_version: str = Field(min_length=1, max_length=120)
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_id_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    client_token_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class MediaObservation(StrictModel):
    post_id: str = Field(min_length=1, max_length=160)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duration_seconds: float = Field(gt=0)
    evidence: tuple[EvidenceRef, ...] = Field(default_factory=tuple)
    receipts: tuple[MediaKitReceipt, ...] = Field(default_factory=tuple)
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_evidence_scope(self) -> MediaObservation:
        ids = [item.evidence_id for item in self.evidence]
        if len(set(ids)) != len(ids):
            raise ValueError("media evidence ids must be unique")
        if any(item.post_id != self.post_id for item in self.evidence):
            raise ValueError("media evidence crosses post boundary")
        if any(receipt.input_sha256 != self.source_sha256 for receipt in self.receipts):
            raise ValueError("MediaKit receipt input hash does not match source")
        return self


class ExtractorReceipt(StrictModel):
    extractor_name: str = Field(min_length=1, max_length=160)
    model_name: str = Field(min_length=1, max_length=160)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


class VideoEvidenceRecord(StrictModel):
    account_ref: str = Field(min_length=1, max_length=500)
    post_id: str = Field(min_length=1, max_length=160)
    source_rights: SourceRights
    rights_ref: str = Field(min_length=1, max_length=1_000)
    captured_at: datetime
    media: MediaObservation
    signals: tuple[SemanticSignal, ...]
    extractor_receipt: ExtractorReceipt

    @model_validator(mode="after")
    def validate_record_scope(self) -> VideoEvidenceRecord:
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        if self.media.post_id != self.post_id:
            raise ValueError("media observation references another post")
        signal_ids = [signal.signal_id for signal in self.signals]
        if len(set(signal_ids)) != len(signal_ids):
            raise ValueError("signal ids must be unique within a video")
        known_refs = {evidence.evidence_id for evidence in self.media.evidence}
        for signal in self.signals:
            if signal.post_id != self.post_id:
                raise ValueError("semantic signal crosses post boundary")
            unknown_refs = set(signal.evidence_refs).difference(known_refs)
            if unknown_refs:
                raise ValueError("semantic signal contains unknown evidence_refs")
        return self


class AggregatedSignal(StrictModel):
    dimension: SignalDimension
    label: str
    epistemic_status: EpistemicStatus
    match_basis: str = Field(pattern=r"^exact_dimension_label_and_status$")
    supporting_post_ids: tuple[str, ...]
    sample_post_ids_without_exact_match: tuple[str, ...]
    support_count: int = Field(ge=1)
    sample_size: int = Field(ge=1)
    sample_support_ratio: float = Field(ge=0, le=1)
    support_status: str = Field(pattern=r"^(single_support|repeated_support)$")
    evidence_refs: tuple[str, ...]

    @model_validator(mode="after")
    def reject_unknown_aggregate(self) -> AggregatedSignal:
        if self.epistemic_status is EpistemicStatus.UNKNOWN:
            raise ValueError("unknown signals cannot become account aggregates")
        return self


class AccountEvidencePack(StrictModel):
    account_ref: str
    source_rights: SourceRights
    rights_ref: str = Field(min_length=1, max_length=1_000)
    generated_at: datetime
    videos: tuple[VideoEvidenceRecord, ...]
    aggregates: tuple[AggregatedSignal, ...]
    limitations: tuple[str, ...] = Field(default_factory=tuple)


class SignalReviewDecision(StrictModel):
    target_signal_id: str = Field(min_length=1, max_length=160)
    disposition: ReviewDisposition
    reason: str = Field(min_length=1, max_length=1_200)
    corrected_signal: SemanticSignal | None = None

    @model_validator(mode="after")
    def validate_correction(self) -> SignalReviewDecision:
        if self.disposition is ReviewDisposition.CORRECTED:
            if self.corrected_signal is None:
                raise ValueError("corrected disposition requires corrected_signal")
            if self.corrected_signal.signal_id != self.target_signal_id:
                raise ValueError("corrected signal must retain target_signal_id")
        elif self.corrected_signal is not None:
            raise ValueError("corrected_signal is allowed only for corrected disposition")
        return self


class TrainingRights(StrictModel):
    source_rights: SourceRights
    allow_model_training: bool
    license_ref: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_training_rights(self) -> TrainingRights:
        if self.source_rights is SourceRights.ANALYSIS_ONLY and self.allow_model_training:
            raise ValueError("analysis-only material cannot authorize model training")
        return self


__all__ = [
    "AccountEvidencePack",
    "AggregatedSignal",
    "EpistemicStatus",
    "EvidenceRef",
    "ExtractorReceipt",
    "MediaKitReceipt",
    "MediaObservation",
    "ReviewDisposition",
    "SemanticSignal",
    "SignalDimension",
    "SignalReviewDecision",
    "SourceRights",
    "TrainingRights",
    "VideoEvidenceRecord",
    "canonical_sha256",
]
