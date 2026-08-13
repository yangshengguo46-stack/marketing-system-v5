from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .audience_evidence import (
    AudienceBehaviorEvent,
    AudienceBehaviorSequence,
    AudienceEvidenceBasis,
    AudienceProfileScope,
    AudienceSignalStatus,
)
from .contracts import StrictModel, canonical_sha256

HLLM_UPSTREAM_COMMIT = "864f17221c04a2d3082d9a072df00616bc7e6dab"
HLLM_ADAPTER_VERSION = "e15-hllm-audience-v1"
HLLM_CREATOR_FIELDS = (
    "user_profile",
    "original_title",
    "original_description",
    "prompt1",
    "prompt2",
    "response",
    "title_list",
    "item_id_list",
)

_AUDIENCE_SEQUENCE_BASES = {
    AudienceEvidenceBasis.AUDIENCE_INTERACTION_SEQUENCE,
    AudienceEvidenceBasis.FOLLOWER_BEHAVIOR_SEQUENCE,
}

_HLLM_PROFILE_OUTPUT_FIELDS = (
    "inference_id",
    "platform",
    "account_id",
    "sequence_id",
    "input_sha256",
    "profile_scope",
    "status",
    "basis",
    "long_term_interests",
    "short_term_interests",
    "needs",
    "content_affinities",
    "supporting_evidence_refs",
    "alternatives",
    "limitations",
    "cluster_ref",
)


def _aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _stable_item_id(*, platform: str, account_id: str, item_id: str) -> int:
    raw = f"{platform}\x00{account_id}\x00{item_id}".encode()
    value = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")
    return value % 2_147_483_646 + 1


def _event_feature(event: AudienceBehaviorEvent) -> str:
    parts = [event.item_text.strip(), f"action={event.action.value}"]
    if event.interaction_text:
        parts.append(f"interaction={event.interaction_text.strip()}")
    return " | ".join(parts)[:8_000]


def hllm_profile_output_sha256(values: object) -> str:
    """Hash the HLLM-owned profile payload without its transport receipt."""

    if isinstance(values, HLLMProfileInference):
        payload = values.model_dump(mode="json", exclude={"receipt"})
    elif isinstance(values, dict):
        payload = {field: values.get(field) for field in _HLLM_PROFILE_OUTPUT_FIELDS}
        payload = HLLMProfileInference.model_construct(
            **payload,
            receipt=None,
        ).model_dump(mode="json", exclude={"receipt"})
    else:
        raise TypeError("HLLM profile output must be a profile or mapping")
    return canonical_sha256(payload)


class HLLMAudienceSequenceItem(StrictModel):
    item_id: int = Field(gt=0)
    feature_text: str = Field(min_length=1, max_length=8_000)
    occurred_at: datetime
    evidence_ref: str = Field(min_length=1, max_length=2_000)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return _aware(value, field_name="occurred_at")


class HLLMProfileInferenceRequest(StrictModel):
    schema_version: Literal["e15-hllm-audience-request-v1"] = "e15-hllm-audience-request-v1"
    platform: str = Field(min_length=1, max_length=80)
    account_id: str = Field(min_length=1, max_length=500)
    sequence_id: str = Field(min_length=1, max_length=500)
    basis: AudienceEvidenceBasis
    items: tuple[HLLMAudienceSequenceItem, ...] = Field(min_length=1, max_length=50)
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    supporting_evidence_refs: tuple[str, ...] = Field(min_length=1, max_length=50)
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    upstream_commit: Literal[HLLM_UPSTREAM_COMMIT] = HLLM_UPSTREAM_COMMIT
    adapter_version: Literal[HLLM_ADAPTER_VERSION] = HLLM_ADAPTER_VERSION
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_request(self) -> HLLMProfileInferenceRequest:
        if self.basis not in _AUDIENCE_SEQUENCE_BASES:
            raise ValueError("HLLM inference requires an audience behavior sequence")
        if len(set(self.supporting_evidence_refs)) != len(self.supporting_evidence_refs):
            raise ValueError("supporting evidence refs must be unique")
        payload = self.model_dump(mode="json", exclude={"input_sha256"})
        if canonical_sha256(payload) != self.input_sha256:
            raise ValueError("HLLM request input hash does not match its payload")
        return self


class HLLMInferenceReceipt(StrictModel):
    model_family: Literal["bytedance_hllm_creator"]
    upstream_commit: Literal[HLLM_UPSTREAM_COMMIT]
    checkpoint_id: str = Field(min_length=1, max_length=500)
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_version: Literal[HLLM_ADAPTER_VERSION]
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        return _aware(value, field_name="generated_at")


class HLLMProfileInference(StrictModel):
    inference_id: str = Field(min_length=1, max_length=500)
    platform: str = Field(min_length=1, max_length=80)
    account_id: str = Field(min_length=1, max_length=500)
    sequence_id: str = Field(min_length=1, max_length=500)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_scope: AudienceProfileScope
    status: AudienceSignalStatus
    basis: AudienceEvidenceBasis
    long_term_interests: tuple[str, ...] = Field(default_factory=tuple)
    short_term_interests: tuple[str, ...] = Field(default_factory=tuple)
    needs: tuple[str, ...] = Field(default_factory=tuple)
    content_affinities: tuple[str, ...] = Field(default_factory=tuple)
    supporting_evidence_refs: tuple[str, ...] = Field(min_length=1, max_length=50)
    alternatives: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    cluster_ref: str | None = Field(default=None, max_length=500)
    receipt: HLLMInferenceReceipt

    @model_validator(mode="after")
    def validate_inference(self) -> HLLMProfileInference:
        if self.profile_scope is not AudienceProfileScope.INFERRED_AUDIENCE_COHORT:
            raise ValueError("HLLM profile must retain inferred audience cohort scope")
        if self.status is not AudienceSignalStatus.INFERRED:
            raise ValueError("HLLM profile is an inference, not an observed audience fact")
        if self.basis not in _AUDIENCE_SEQUENCE_BASES:
            raise ValueError("HLLM profile requires an audience behavior sequence")
        if self.receipt.input_sha256 != self.input_sha256:
            raise ValueError("HLLM receipt input hash does not match profile input hash")
        if self.receipt.output_sha256 != hllm_profile_output_sha256(self):
            raise ValueError("HLLM receipt output hash does not match profile output hash")
        if len(set(self.supporting_evidence_refs)) != len(self.supporting_evidence_refs):
            raise ValueError("supporting evidence refs must be unique")
        return self


class HLLMAudienceAdapter:
    """Translate real audience behavior sequences into the upstream HLLM contract."""

    def __init__(self, *, max_history: int = 50) -> None:
        if not 1 <= max_history <= 50:
            raise ValueError("max_history must be between 1 and 50")
        self.max_history = max_history

    def _recent_events(self, sequence: AudienceBehaviorSequence) -> tuple[AudienceBehaviorEvent, ...]:
        if sequence.basis not in _AUDIENCE_SEQUENCE_BASES:
            raise ValueError("HLLM requires an audience behavior sequence; account performance is only a proxy")
        ordered = sorted(sequence.events, key=lambda event: (event.occurred_at, event.event_id))
        return tuple(ordered[-self.max_history :])

    def build_creator_row(
        self,
        *,
        sequence: AudienceBehaviorSequence,
        target_title: str,
        target_description: str,
    ) -> dict[str, object]:
        recent = self._recent_events(sequence)
        title = target_title.strip()
        description = target_description.strip()
        if not title:
            raise ValueError("target_title is required")
        if not description:
            raise ValueError("target_description is required")
        values: dict[str, object] = {
            "user_profile": "{}",
            "original_title": title[:2_000],
            "original_description": description[:8_000],
            "prompt1": ("The preceding features are one pseudonymous audience sequence, ordered from oldest to newest. Model interests without treating the sample as the whole audience."),
            "prompt2": "Generate or reconstruct only from the supplied audience sequence:",
            "response": "",
            "title_list": [_event_feature(event) for event in recent],
            "item_id_list": [
                _stable_item_id(
                    platform=event.platform,
                    account_id=event.account_id,
                    item_id=event.item_id,
                )
                for event in recent
            ],
        }
        return {field: values[field] for field in HLLM_CREATOR_FIELDS}

    def build_inference_request(
        self,
        *,
        sequence: AudienceBehaviorSequence,
    ) -> HLLMProfileInferenceRequest:
        recent = self._recent_events(sequence)
        items = tuple(
            HLLMAudienceSequenceItem(
                item_id=_stable_item_id(
                    platform=event.platform,
                    account_id=event.account_id,
                    item_id=event.item_id,
                ),
                feature_text=_event_feature(event),
                occurred_at=event.occurred_at,
                evidence_ref=event.evidence_ref,
            )
            for event in recent
        )
        values = {
            "schema_version": "e15-hllm-audience-request-v1",
            "platform": sequence.platform,
            "account_id": sequence.account_id,
            "sequence_id": sequence.sequence_id,
            "basis": sequence.basis,
            "items": items,
            "source_snapshot_sha256": sequence.source_snapshot_sha256,
            "supporting_evidence_refs": tuple(item.evidence_ref for item in items),
            "limitations": sequence.limitations,
            "upstream_commit": HLLM_UPSTREAM_COMMIT,
            "adapter_version": HLLM_ADAPTER_VERSION,
        }
        input_sha256 = canonical_sha256(
            HLLMProfileInferenceRequest.model_construct(
                **values,
                input_sha256="0" * 64,
            ).model_dump(mode="json", exclude={"input_sha256"})
        )
        return HLLMProfileInferenceRequest(**values, input_sha256=input_sha256)


__all__ = [
    "HLLM_ADAPTER_VERSION",
    "HLLM_CREATOR_FIELDS",
    "HLLM_UPSTREAM_COMMIT",
    "HLLMAudienceAdapter",
    "HLLMAudienceSequenceItem",
    "HLLMInferenceReceipt",
    "HLLMProfileInference",
    "HLLMProfileInferenceRequest",
    "hllm_profile_output_sha256",
]
