from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from .contracts import SourceRights, StrictModel, canonical_sha256


class CollectionMethod(StrEnum):
    MANUAL_PUBLIC_OBSERVATION = "manual_public_observation"
    VISIBLE_BROWSER_AUTHORIZED = "visible_browser_authorized"
    USER_EXPORT = "user_export"
    USER_UPLOAD = "user_upload"
    FIRST_PARTY_AUTHORIZED = "first_party_authorized"


def _aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _public_http_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("URL must not contain credentials")
    return value


def _validate_public_metrics(
    value: dict[str, int | float],
) -> dict[str, int | float]:
    for name, metric in value.items():
        if not name or len(name) > 80:
            raise ValueError("public metric names must be between 1 and 80 characters")
        if isinstance(metric, bool) or not isfinite(metric) or metric < 0:
            raise ValueError("public metrics must be finite non-negative numbers")
    return value


class AccountProfileObservation(StrictModel):
    platform: str = Field(min_length=1, max_length=80)
    account_id: str = Field(min_length=1, max_length=240)
    canonical_url: str = Field(min_length=1, max_length=1_000)
    display_name: str | None = Field(default=None, min_length=1, max_length=300)
    bio: str | None = Field(default=None, max_length=2_000)
    verification: str | None = Field(default=None, max_length=500)
    visible_work_count: int | None = Field(default=None, ge=0)
    public_metrics: dict[str, int | float] = Field(default_factory=dict)
    captured_at: datetime

    @field_validator("canonical_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _public_http_url(value)

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _aware(value, field_name="captured_at")

    @field_validator("public_metrics")
    @classmethod
    def validate_public_metrics(cls, value: dict[str, int | float]) -> dict[str, int | float]:
        return _validate_public_metrics(value)


class PostListObservation(StrictModel):
    post_id: str = Field(min_length=1, max_length=240)
    canonical_url: str = Field(min_length=1, max_length=1_000)
    caption: str | None = Field(default=None, max_length=4_000)
    published_at: datetime | None = None
    captured_at: datetime
    public_metrics: dict[str, int | float] = Field(default_factory=dict)
    media_artifact_ref: str | None = Field(default=None, max_length=1_000)

    @field_validator("canonical_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _public_http_url(value)

    @field_validator("published_at", "captured_at")
    @classmethod
    def validate_timestamp(cls, value: datetime | None, info) -> datetime | None:
        if value is None:
            return None
        return _aware(value, field_name=info.field_name)

    @field_validator("public_metrics")
    @classmethod
    def validate_metrics(cls, value: dict[str, int | float]) -> dict[str, int | float]:
        return _validate_public_metrics(value)

    @field_validator("media_artifact_ref")
    @classmethod
    def validate_artifact_ref(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("artifact://"):
            raise ValueError("media_artifact_ref must use an artifact:// handle")
        return value


class AccountSourceSnapshot(StrictModel):
    profile: AccountProfileObservation
    posts: tuple[PostListObservation, ...] = Field(default_factory=tuple)
    collection_method: CollectionMethod
    source_rights: SourceRights
    rights_ref: str = Field(min_length=1, max_length=1_000)
    requested_url: str = Field(min_length=1, max_length=1_000)
    sample_basis: str = Field(min_length=1, max_length=2_000)
    captured_at: datetime
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("requested_url")
    @classmethod
    def validate_requested_url(cls, value: str) -> str:
        return _public_http_url(value)

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
    def validate_snapshot(self) -> AccountSourceSnapshot:
        post_ids = [post.post_id for post in self.posts]
        if len(set(post_ids)) != len(post_ids):
            raise ValueError("post ids must be unique within a source snapshot")
        if any(post.captured_at > self.captured_at for post in self.posts):
            raise ValueError("post capture cannot occur after snapshot capture")
        if self.profile.captured_at > self.captured_at:
            raise ValueError("profile capture cannot occur after snapshot capture")
        return self


@dataclass(frozen=True, slots=True)
class SnapshotCacheResult:
    snapshot_sha256: str
    path: Path
    cache_hit: bool


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("._-")
    return cleaned[:100] or canonical_sha256(value)[:20]


def cache_account_source_snapshot(
    snapshot: AccountSourceSnapshot,
    *,
    cache_root: Path,
) -> SnapshotCacheResult:
    payload = snapshot.model_dump(mode="json")
    snapshot_sha256 = canonical_sha256(payload)
    target = cache_root.expanduser().resolve() / _safe_component(snapshot.profile.platform) / _safe_component(snapshot.profile.account_id) / snapshot_sha256 / "snapshot.json"
    if target.is_file():
        return SnapshotCacheResult(snapshot_sha256=snapshot_sha256, path=target, cache_hit=True)

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    try:
        temporary.replace(target)
    except OSError:
        temporary.unlink(missing_ok=True)
        if not target.is_file():
            raise
        return SnapshotCacheResult(snapshot_sha256=snapshot_sha256, path=target, cache_hit=True)
    return SnapshotCacheResult(snapshot_sha256=snapshot_sha256, path=target, cache_hit=False)


__all__ = [
    "AccountProfileObservation",
    "AccountSourceSnapshot",
    "CollectionMethod",
    "PostListObservation",
    "SnapshotCacheResult",
    "cache_account_source_snapshot",
]
