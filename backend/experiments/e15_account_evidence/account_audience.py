from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from .audience_collection import (
    AudienceCollectionSnapshot,
    AudienceMetricNature,
    AudienceMetricObservation,
    derive_longitudinal_audience_metrics,
)
from .audience_evidence import (
    AudienceAggregateSnapshot,
    AudienceBehaviorSequence,
    build_audience_behavior_sequences,
)
from .contracts import StrictModel, canonical_sha256
from .hllm_audience import HLLMProfileInference
from .source_snapshot import AccountSourceSnapshot


class AccountAudienceIntelligencePack(StrictModel):
    """Account audience intelligence with explicit collection and inference layers."""

    platform: str = Field(min_length=1, max_length=80)
    account_id: str = Field(min_length=1, max_length=500)
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    collection_snapshots: tuple[AudienceCollectionSnapshot, ...] = Field(default_factory=tuple)
    derived_metrics: tuple[AudienceMetricObservation, ...] = Field(default_factory=tuple)
    aggregate_snapshots: tuple[AudienceAggregateSnapshot, ...] = Field(default_factory=tuple)
    behavior_sequences: tuple[AudienceBehaviorSequence, ...] = Field(default_factory=tuple)
    hllm_profiles: tuple[HLLMProfileInference, ...] = Field(default_factory=tuple)
    generated_at: datetime
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 1_200 for item in value):
            raise ValueError("limitations must be non-empty and at most 1200 characters")
        return value

    @model_validator(mode="after")
    def validate_pack_scope(self) -> AccountAudienceIntelligencePack:
        for snapshot in self.collection_snapshots:
            if snapshot.platform.value != self.platform or snapshot.account_id != self.account_id:
                raise ValueError("audience collection crosses account boundary")
            if snapshot.source_account_snapshot_sha256 != self.source_snapshot_sha256:
                raise ValueError("audience collection references another source snapshot")
            if snapshot.captured_at > self.generated_at:
                raise ValueError("audience collection cannot occur after pack generation")
        for metric in self.derived_metrics:
            if metric.nature is not AudienceMetricNature.DERIVED:
                raise ValueError("derived_metrics contains a non-derived metric")
            if metric.captured_at > self.generated_at:
                raise ValueError("derived audience metric cannot occur after pack generation")
        for snapshot in self.aggregate_snapshots:
            if snapshot.platform != self.platform or snapshot.account_id != self.account_id:
                raise ValueError("audience aggregate crosses account boundary")
            if snapshot.source_snapshot_sha256 != self.source_snapshot_sha256:
                raise ValueError("audience aggregate references another source snapshot")
        for sequence in self.behavior_sequences:
            if sequence.platform != self.platform or sequence.account_id != self.account_id:
                raise ValueError("audience sequence crosses account boundary")
            if sequence.source_snapshot_sha256 != self.source_snapshot_sha256:
                raise ValueError("audience sequence references another source snapshot")

        sequence_by_id = {sequence.sequence_id: sequence for sequence in self.behavior_sequences}
        if len(sequence_by_id) != len(self.behavior_sequences):
            raise ValueError("audience sequence ids must be unique")
        inference_ids = [profile.inference_id for profile in self.hllm_profiles]
        if len(set(inference_ids)) != len(inference_ids):
            raise ValueError("HLLM inference ids must be unique")
        for profile in self.hllm_profiles:
            if profile.platform != self.platform or profile.account_id != self.account_id:
                raise ValueError("HLLM profile crosses account boundary")
            sequence = sequence_by_id.get(profile.sequence_id)
            if sequence is None:
                raise ValueError("HLLM profile references an unknown sequence")
            if profile.basis is not sequence.basis:
                raise ValueError("HLLM profile basis does not match its sequence")
            sequence_refs = {event.evidence_ref for event in sequence.events}
            if not set(profile.supporting_evidence_refs).issubset(sequence_refs):
                raise ValueError("HLLM profile references evidence outside its sequence")
        return self

    @property
    def collection_snapshot_count(self) -> int:
        return len(self.collection_snapshots)

    @property
    def observed_aggregate_count(self) -> int:
        return len(self.aggregate_snapshots)

    @property
    def behavior_sequence_count(self) -> int:
        return len(self.behavior_sequences)

    @property
    def hllm_profile_count(self) -> int:
        return len(self.hllm_profiles)


def build_account_audience_intelligence_pack(
    *,
    source: AccountSourceSnapshot,
    collection_snapshots: tuple[AudienceCollectionSnapshot, ...],
    generated_at: datetime,
    aggregate_snapshots: tuple[AudienceAggregateSnapshot, ...] = (),
    hllm_profiles: tuple[HLLMProfileInference, ...] = (),
) -> AccountAudienceIntelligencePack:
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    source_sha256 = canonical_sha256(source.model_dump(mode="json"))
    expected_platform = source.profile.platform
    expected_account_id = source.profile.account_id
    source_post_ids = {post.post_id for post in source.posts}
    ordered_collections = tuple(sorted(collection_snapshots, key=lambda item: item.captured_at))
    all_interactions = []
    for snapshot in ordered_collections:
        if snapshot.platform.value != expected_platform or snapshot.account_id != expected_account_id:
            raise ValueError("audience collection belongs to another account")
        if snapshot.source_account_snapshot_sha256 != source_sha256:
            raise ValueError("audience collection belongs to another source snapshot")
        outside = sorted({interaction.item_id for interaction in snapshot.interactions if interaction.item_id not in source_post_ids})
        if outside:
            raise ValueError("audience interaction references a post outside the account snapshot")
        all_interactions.extend(snapshot.interactions)

    seen_interactions = set()
    unique_interactions = []
    for interaction in sorted(
        all_interactions,
        key=lambda item: (
            item.occurred_at or item.captured_at,
            item.interaction_id,
        ),
    ):
        if interaction.interaction_id in seen_interactions:
            continue
        seen_interactions.add(interaction.interaction_id)
        unique_interactions.append(interaction)
    behavior_sequences = build_audience_behavior_sequences(
        interactions=tuple(unique_interactions),
        source_snapshot_sha256=source_sha256,
    )

    derived_metrics = []
    for previous, current in zip(ordered_collections, ordered_collections[1:]):
        derived_metrics.extend(derive_longitudinal_audience_metrics(previous=previous, current=current))
    limitations = [
        "Audience intelligence coverage follows each dataset receipt; unavailable data is not inferred as observed fact.",
    ]
    if not behavior_sequences:
        limitations.append("No actor-linked audience interaction sequence was available.")
    if not hllm_profiles:
        limitations.append("No accepted HLLM checkpoint inference is attached.")
    return AccountAudienceIntelligencePack(
        platform=expected_platform,
        account_id=expected_account_id,
        source_snapshot_sha256=source_sha256,
        collection_snapshots=ordered_collections,
        derived_metrics=tuple(derived_metrics),
        aggregate_snapshots=aggregate_snapshots,
        behavior_sequences=behavior_sequences,
        hllm_profiles=hllm_profiles,
        generated_at=generated_at,
        limitations=tuple(limitations),
    )


# Compatibility name for the first isolated HLLM contract. New code should use
# AccountAudienceIntelligencePack.
AccountAudienceEvidencePack = AccountAudienceIntelligencePack


__all__ = [
    "AccountAudienceEvidencePack",
    "AccountAudienceIntelligencePack",
    "build_account_audience_intelligence_pack",
]
