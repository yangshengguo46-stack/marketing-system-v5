from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator, model_validator

from .contracts import SourceRights, StrictModel
from .source_snapshot import (
    AccountProfileObservation,
    AccountSourceSnapshot,
    CollectionMethod,
    PostListObservation,
    SnapshotCacheResult,
    cache_account_source_snapshot,
)


class AccountLinkCollectionRequest(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)
    requested_url: str = Field(min_length=1, max_length=1_000)
    collection_method: CollectionMethod
    source_rights: SourceRights
    rights_ref: str = Field(min_length=1, max_length=1_000)
    max_posts: int = Field(default=12, ge=1, le=24)
    cache_root: Path

    @field_validator("requested_url")
    @classmethod
    def validate_requested_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("requested_url must be an absolute http or https URL")
        if parsed.username or parsed.password:
            raise ValueError("requested_url must not contain credentials")
        return value

    @field_validator("cache_root")
    @classmethod
    def resolve_cache_root(cls, value: Path) -> Path:
        return value.expanduser().resolve()


class StructuredAccountObservation(StrictModel):
    profile: AccountProfileObservation
    posts: tuple[PostListObservation, ...] = Field(default_factory=tuple)
    final_url: str = Field(min_length=1, max_length=1_000)
    sample_basis: str = Field(min_length=1, max_length=2_000)
    captured_at: datetime
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_observation(self) -> StructuredAccountObservation:
        post_ids = [post.post_id for post in self.posts]
        if len(set(post_ids)) != len(post_ids):
            raise ValueError("post ids must be unique within a structured observation")
        return self


class AccountLinkCollector(Protocol):
    def __call__(
        self,
        *,
        requested_url: str,
        max_posts: int,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class AccountLinkCollectionResult:
    snapshot: AccountSourceSnapshot
    cache: SnapshotCacheResult


async def _await_if_needed(value: object) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def collect_account_link(
    request: AccountLinkCollectionRequest,
    *,
    collector: AccountLinkCollector | Callable[..., object],
) -> AccountLinkCollectionResult:
    raw = collector(
        requested_url=request.requested_url,
        max_posts=request.max_posts,
    )
    observation = StructuredAccountObservation.model_validate(await _await_if_needed(raw))
    if len(observation.posts) > request.max_posts:
        raise ValueError("collector exceeded max_posts")

    snapshot = AccountSourceSnapshot(
        profile=observation.profile,
        posts=observation.posts,
        collection_method=request.collection_method,
        source_rights=request.source_rights,
        rights_ref=request.rights_ref,
        requested_url=request.requested_url,
        sample_basis=observation.sample_basis,
        captured_at=observation.captured_at,
        limitations=observation.limitations,
    )
    cache = cache_account_source_snapshot(snapshot, cache_root=request.cache_root)
    return AccountLinkCollectionResult(snapshot=snapshot, cache=cache)


__all__ = [
    "AccountLinkCollectionRequest",
    "AccountLinkCollectionResult",
    "AccountLinkCollector",
    "StructuredAccountObservation",
    "collect_account_link",
]
