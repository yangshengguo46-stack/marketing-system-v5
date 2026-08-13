from __future__ import annotations

import hashlib
import hmac
from collections import defaultdict
from datetime import datetime
from enum import StrEnum
from math import isfinite

from pydantic import Field, field_validator, model_validator

from .contracts import StrictModel, canonical_sha256


class AudienceEvidenceBasis(StrEnum):
    PLATFORM_AGGREGATE_ANALYTICS = "platform_aggregate_analytics"
    AUDIENCE_INTERACTION_SEQUENCE = "audience_interaction_sequence"
    FOLLOWER_BEHAVIOR_SEQUENCE = "follower_behavior_sequence"
    ACCOUNT_CONTENT_PERFORMANCE_PROXY = "account_content_performance_proxy"


class AudienceProfileScope(StrEnum):
    PLATFORM_OBSERVED_AUDIENCE = "platform_observed_audience"
    INFERRED_AUDIENCE_COHORT = "inferred_audience_cohort"
    ACCOUNT_RESPONSE_PROXY = "account_response_proxy"


class AudienceSignalStatus(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"


class AudienceBehaviorAction(StrEnum):
    VIEW = "view"
    LIKE = "like"
    COMMENT = "comment"
    REPLY = "reply"
    SHARE = "share"
    SAVE = "save"
    FOLLOW = "follow"
    LIVE_ENTER = "live_enter"
    LIVE_CHAT = "live_chat"
    PRODUCT_CLICK = "product_click"
    ADD_TO_CART = "add_to_cart"
    PURCHASE = "purchase"


class AudienceInteractionKind(StrEnum):
    VIEW = "view"
    LIKE = "like"
    COMMENT = "comment"
    REPLY = "reply"
    SHARE = "share"
    SAVE = "save"
    FOLLOW = "follow"
    LIVE_ENTER = "live_enter"
    LIVE_CHAT = "live_chat"
    PRODUCT_CLICK = "product_click"
    ADD_TO_CART = "add_to_cart"
    PURCHASE = "purchase"


_INTERACTION_TO_ACTION = {
    AudienceInteractionKind.VIEW: AudienceBehaviorAction.VIEW,
    AudienceInteractionKind.LIKE: AudienceBehaviorAction.LIKE,
    AudienceInteractionKind.COMMENT: AudienceBehaviorAction.COMMENT,
    AudienceInteractionKind.REPLY: AudienceBehaviorAction.REPLY,
    AudienceInteractionKind.SHARE: AudienceBehaviorAction.SHARE,
    AudienceInteractionKind.SAVE: AudienceBehaviorAction.SAVE,
    AudienceInteractionKind.FOLLOW: AudienceBehaviorAction.FOLLOW,
    AudienceInteractionKind.LIVE_ENTER: AudienceBehaviorAction.LIVE_ENTER,
    AudienceInteractionKind.LIVE_CHAT: AudienceBehaviorAction.LIVE_CHAT,
    AudienceInteractionKind.PRODUCT_CLICK: AudienceBehaviorAction.PRODUCT_CLICK,
    AudienceInteractionKind.ADD_TO_CART: AudienceBehaviorAction.ADD_TO_CART,
    AudienceInteractionKind.PURCHASE: AudienceBehaviorAction.PURCHASE,
}


class AudienceAggregateValueKind(StrEnum):
    COUNT = "count"
    RATIO = "ratio"
    INDEX = "index"


def _aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def pseudonymous_actor_ref(
    *,
    platform: str,
    raw_actor_id: str,
    local_salt: str,
) -> str:
    """Create a stable local join key without retaining the platform actor id."""

    normalized_platform = platform.strip().lower()
    normalized_actor_id = raw_actor_id.strip()
    if not normalized_platform:
        raise ValueError("platform is required")
    if not normalized_actor_id:
        raise ValueError("raw_actor_id is required")
    if not local_salt:
        raise ValueError("local_salt is required")
    digest = hmac.new(
        local_salt.encode("utf-8"),
        f"{normalized_platform}\x00{normalized_actor_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"actor://sha256/{digest}"


class AudienceBehaviorEvent(StrictModel):
    event_id: str = Field(min_length=1, max_length=500)
    platform: str = Field(min_length=1, max_length=80)
    account_id: str = Field(min_length=1, max_length=500)
    actor_ref: str = Field(pattern=r"^actor://sha256/[0-9a-f]{64}$")
    action: AudienceBehaviorAction
    item_id: str = Field(min_length=1, max_length=500)
    item_text: str = Field(min_length=1, max_length=8_000)
    interaction_text: str | None = Field(default=None, max_length=8_000)
    occurred_at: datetime
    captured_at: datetime
    evidence_ref: str = Field(min_length=1, max_length=2_000)

    @field_validator("occurred_at", "captured_at")
    @classmethod
    def validate_timestamps(cls, value: datetime, info) -> datetime:
        return _aware(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_capture_order(self) -> AudienceBehaviorEvent:
        if self.captured_at < self.occurred_at:
            raise ValueError("captured_at cannot precede occurred_at")
        return self


class AudienceInteractionObservation(StrictModel):
    """One audience interaction after the actor id has been pseudonymized."""

    interaction_id: str = Field(min_length=1, max_length=500)
    platform: str = Field(min_length=1, max_length=80)
    account_id: str = Field(min_length=1, max_length=500)
    item_id: str = Field(min_length=1, max_length=500)
    item_text: str = Field(min_length=1, max_length=8_000)
    kind: AudienceInteractionKind
    actor_ref: str = Field(pattern=r"^actor://sha256/[0-9a-f]{64}$")
    text: str | None = Field(default=None, max_length=8_000)
    public_metrics: dict[str, int | float] = Field(default_factory=dict)
    occurred_at: datetime | None = None
    captured_at: datetime
    evidence_ref: str = Field(min_length=1, max_length=2_000)

    @classmethod
    def from_raw_actor(
        cls,
        *,
        raw_actor_id: str,
        local_salt: str,
        **values: object,
    ) -> AudienceInteractionObservation:
        """Pseudonymize an actor at the collection boundary before persistence."""

        if "actor_ref" in values:
            raise ValueError("actor_ref cannot be supplied with raw_actor_id")
        platform = str(values.get("platform") or "")
        return cls(
            **values,
            actor_ref=pseudonymous_actor_ref(
                platform=platform,
                raw_actor_id=raw_actor_id,
                local_salt=local_salt,
            ),
        )

    @field_validator("occurred_at", "captured_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None, info) -> datetime | None:
        if value is None:
            return None
        return _aware(value, field_name=info.field_name)

    @field_validator("public_metrics")
    @classmethod
    def validate_public_metrics(
        cls,
        value: dict[str, int | float],
    ) -> dict[str, int | float]:
        for name, metric in value.items():
            if not name or len(name) > 80:
                raise ValueError("public metric names must be between 1 and 80 characters")
            if isinstance(metric, bool) or not isfinite(metric) or metric < 0:
                raise ValueError("public metrics must be finite non-negative numbers")
        return value

    @model_validator(mode="after")
    def validate_capture_order(self) -> AudienceInteractionObservation:
        if self.occurred_at is not None and self.captured_at < self.occurred_at:
            raise ValueError("captured_at cannot precede occurred_at")
        if self.kind in {AudienceInteractionKind.COMMENT, AudienceInteractionKind.REPLY, AudienceInteractionKind.LIVE_CHAT} and not self.text:
            raise ValueError("text interaction requires text")
        return self


class AudienceBehaviorSequence(StrictModel):
    sequence_id: str = Field(min_length=1, max_length=500)
    platform: str = Field(min_length=1, max_length=80)
    account_id: str = Field(min_length=1, max_length=500)
    actor_ref: str = Field(pattern=r"^actor://sha256/[0-9a-f]{64}$")
    basis: AudienceEvidenceBasis
    events: tuple[AudienceBehaviorEvent, ...] = Field(min_length=1, max_length=500)
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_basis: str = Field(min_length=1, max_length=2_000)
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 1_200 for item in value):
            raise ValueError("limitations must be non-empty and at most 1200 characters")
        return value

    @model_validator(mode="after")
    def validate_sequence_scope(self) -> AudienceBehaviorSequence:
        event_ids = [event.event_id for event in self.events]
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("event ids must be unique within an audience sequence")
        if any(event.platform != self.platform for event in self.events):
            raise ValueError("audience sequence contains an event from another platform")
        if any(event.account_id != self.account_id for event in self.events):
            raise ValueError("audience sequence contains an event from another account")
        if any(event.actor_ref != self.actor_ref for event in self.events):
            raise ValueError("audience sequence contains an event from another actor")
        return self

    @property
    def profile_scope(self) -> AudienceProfileScope:
        if self.basis is AudienceEvidenceBasis.ACCOUNT_CONTENT_PERFORMANCE_PROXY:
            return AudienceProfileScope.ACCOUNT_RESPONSE_PROXY
        return AudienceProfileScope.INFERRED_AUDIENCE_COHORT


def build_audience_behavior_sequences(
    *,
    interactions: tuple[AudienceInteractionObservation, ...],
    source_snapshot_sha256: str,
) -> tuple[AudienceBehaviorSequence, ...]:
    """Group collected audience interactions into pseudonymous sequences."""

    if not interactions:
        return ()
    if len(source_snapshot_sha256) != 64 or any(character not in "0123456789abcdef" for character in source_snapshot_sha256):
        raise ValueError("source_snapshot_sha256 must be a lowercase SHA-256 digest")
    platforms = {interaction.platform for interaction in interactions}
    account_ids = {interaction.account_id for interaction in interactions}
    if len(platforms) != 1 or len(account_ids) != 1:
        raise ValueError("interactions must belong to one account on one platform")
    interaction_ids = [interaction.interaction_id for interaction in interactions]
    if len(set(interaction_ids)) != len(interaction_ids):
        raise ValueError("interaction ids must be unique")

    platform = next(iter(platforms))
    account_id = next(iter(account_ids))
    grouped: dict[str, list[AudienceInteractionObservation]] = defaultdict(list)
    for interaction in interactions:
        grouped[interaction.actor_ref].append(interaction)

    sequences: list[AudienceBehaviorSequence] = []
    for actor_ref, actor_interactions in grouped.items():
        ordered = sorted(
            actor_interactions,
            key=lambda interaction: (
                interaction.occurred_at or interaction.captured_at,
                interaction.interaction_id,
            ),
        )
        events = tuple(
            AudienceBehaviorEvent(
                event_id=interaction.interaction_id,
                platform=platform,
                account_id=account_id,
                actor_ref=actor_ref,
                action=_INTERACTION_TO_ACTION[interaction.kind],
                item_id=interaction.item_id,
                item_text=interaction.item_text,
                interaction_text=interaction.text,
                occurred_at=interaction.occurred_at or interaction.captured_at,
                captured_at=interaction.captured_at,
                evidence_ref=interaction.evidence_ref,
            )
            for interaction in ordered
        )
        limitations = [
            "The sequence contains only audience interactions visible in the bounded account sample.",
        ]
        if any(interaction.occurred_at is None for interaction in ordered):
            limitations.append("At least one interaction lacked an event time; capture time was used for ordering.")
        if len(events) < 2:
            limitations.append("HLLM received a short sequence; treat any profile as very low-coverage evidence.")
        sequence_digest = canonical_sha256(
            {
                "platform": platform,
                "account_id": account_id,
                "actor_ref": actor_ref,
                "source_snapshot_sha256": source_snapshot_sha256,
                "event_ids": [event.event_id for event in events],
            }
        )
        sequences.append(
            AudienceBehaviorSequence(
                sequence_id=f"audseq-{sequence_digest}",
                platform=platform,
                account_id=account_id,
                actor_ref=actor_ref,
                basis=AudienceEvidenceBasis.AUDIENCE_INTERACTION_SEQUENCE,
                events=events,
                source_snapshot_sha256=source_snapshot_sha256,
                sample_basis="Collected audience interactions grouped by one local pseudonymous actor reference.",
                limitations=tuple(limitations),
            )
        )
    return tuple(sorted(sequences, key=lambda item: (-len(item.events), item.actor_ref)))


class AudienceAggregateSlice(StrictModel):
    dimension: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=500)
    value: float = Field(ge=0)
    value_kind: AudienceAggregateValueKind
    evidence_ref: str = Field(min_length=1, max_length=2_000)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("aggregate value must be finite")
        return value

    @model_validator(mode="after")
    def validate_kind(self) -> AudienceAggregateSlice:
        if self.value_kind is AudienceAggregateValueKind.RATIO and self.value > 1:
            raise ValueError("ratio aggregate value cannot exceed 1")
        if self.value_kind is AudienceAggregateValueKind.COUNT and not self.value.is_integer():
            raise ValueError("count aggregate value must be an integer")
        return self


class AudienceAggregateSnapshot(StrictModel):
    platform: str = Field(min_length=1, max_length=80)
    account_id: str = Field(min_length=1, max_length=500)
    basis: AudienceEvidenceBasis
    profile_scope: AudienceProfileScope = AudienceProfileScope.PLATFORM_OBSERVED_AUDIENCE
    status: AudienceSignalStatus
    slices: tuple[AudienceAggregateSlice, ...] = Field(min_length=1, max_length=1_000)
    captured_at: datetime
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _aware(value, field_name="captured_at")

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 1_200 for item in value):
            raise ValueError("limitations must be non-empty and at most 1200 characters")
        return value

    @model_validator(mode="after")
    def validate_platform_aggregate(self) -> AudienceAggregateSnapshot:
        if self.basis is not AudienceEvidenceBasis.PLATFORM_AGGREGATE_ANALYTICS:
            raise ValueError("platform aggregate snapshot requires platform aggregate analytics")
        if self.profile_scope is not AudienceProfileScope.PLATFORM_OBSERVED_AUDIENCE:
            raise ValueError("platform aggregate must retain the observed audience scope")
        if self.status is not AudienceSignalStatus.OBSERVED:
            raise ValueError("platform aggregate analytics must remain observed evidence")
        slice_keys = [(item.dimension, item.label) for item in self.slices]
        if len(set(slice_keys)) != len(slice_keys):
            raise ValueError("platform aggregate slices must be unique")
        return self


__all__ = [
    "AudienceAggregateSlice",
    "AudienceAggregateSnapshot",
    "AudienceAggregateValueKind",
    "AudienceBehaviorAction",
    "AudienceBehaviorEvent",
    "AudienceBehaviorSequence",
    "AudienceEvidenceBasis",
    "AudienceInteractionKind",
    "AudienceInteractionObservation",
    "AudienceProfileScope",
    "AudienceSignalStatus",
    "build_audience_behavior_sequences",
    "pseudonymous_actor_ref",
]
