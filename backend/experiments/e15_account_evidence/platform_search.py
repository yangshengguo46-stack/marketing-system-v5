from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import Any, Protocol
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, field_validator, model_validator

from .contracts import StrictModel
from .local_browser_credentials import (
    InvalidLocalBrowserCredential,
    LocalBrowserCredentialNotFound,
    LocalBrowserCredentialProvider,
    LocalBrowserCredentials,
)


class SearchPlatform(StrEnum):
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    WECHAT_CHANNELS = "wechat_channels"
    KUAISHOU = "kuaishou"
    BILIBILI = "bilibili"
    TIKTOK = "tiktok"


SUPPORTED_SEARCH_PLATFORMS = (
    SearchPlatform.DOUYIN,
    SearchPlatform.XIAOHONGSHU,
    SearchPlatform.WECHAT_CHANNELS,
    SearchPlatform.KUAISHOU,
    SearchPlatform.BILIBILI,
    SearchPlatform.TIKTOK,
)


class PlatformSearchTarget(StrEnum):
    CONTENT = "content"
    ACCOUNTS = "accounts"
    ACCOUNT_POSTS = "account_posts"


class PlatformSearchItemType(StrEnum):
    POST = "post"
    ACCOUNT = "account"


class PlatformSearchStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NEEDS_LOGIN = "needs_login"
    RESTRICTED = "restricted"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    SCHEMA_DRIFT = "schema_drift"


class PlatformSearchSource(StrEnum):
    PUBLIC_BROWSER = "public_browser"
    AUTHENTICATED_BROWSER = "authenticated_browser"
    OFFICIAL_API = "official_api"
    DESKTOP_CLIENT = "desktop_client"
    USER_EXPORT = "user_export"
    UNKNOWN = "unknown"


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


class PlatformSearchRequest(StrictModel):
    platform: SearchPlatform
    target: PlatformSearchTarget
    query: str = Field(min_length=1, max_length=500)
    page_size: int = Field(default=30, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=2_000)
    session_ref: str | None = Field(default=None, min_length=1, max_length=240)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized


class PlatformSearchItem(StrictModel):
    platform: SearchPlatform
    item_type: PlatformSearchItemType
    item_id: str = Field(min_length=1, max_length=500)
    canonical_url: str = Field(min_length=1, max_length=2_000)
    title: str | None = Field(default=None, max_length=2_000)
    description: str | None = Field(default=None, max_length=8_000)
    author_id: str | None = Field(default=None, max_length=500)
    author_name: str | None = Field(default=None, max_length=500)
    author_public_metrics: dict[str, int | float] = Field(default_factory=dict)
    published_at: datetime | None = None
    captured_at: datetime
    public_metrics: dict[str, int | float] = Field(default_factory=dict)
    thumbnail_url: str | None = Field(default=None, max_length=2_000)

    @field_validator("canonical_url")
    @classmethod
    def validate_canonical_url(cls, value: str) -> str:
        return _public_http_url(value)

    @field_validator("thumbnail_url")
    @classmethod
    def validate_thumbnail_url(cls, value: str | None) -> str | None:
        return _public_http_url(value) if value is not None else None

    @field_validator("published_at", "captured_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None, info) -> datetime | None:
        if value is None:
            return None
        return _aware(value, field_name=info.field_name)

    @field_validator("public_metrics", "author_public_metrics")
    @classmethod
    def validate_public_metrics(cls, value: dict[str, int | float]) -> dict[str, int | float]:
        for name, metric in value.items():
            if not name or len(name) > 80:
                raise ValueError("public metric names must be between 1 and 80 characters")
            if isinstance(metric, bool) or not isfinite(metric) or metric < 0:
                raise ValueError("public metrics must be finite non-negative numbers")
        return value


class PlatformSearchPage(StrictModel):
    platform: SearchPlatform
    target: PlatformSearchTarget
    query: str = Field(min_length=1, max_length=500)
    requested_page_size: int = Field(ge=1, le=100)
    status: PlatformSearchStatus
    source: PlatformSearchSource
    capability_version: str = Field(min_length=1, max_length=240)
    authenticated: bool
    items: tuple[PlatformSearchItem, ...] = Field(default_factory=tuple)
    next_cursor: str | None = Field(default=None, max_length=2_000)
    captured_at: datetime
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    error_code: str | None = Field(default=None, max_length=160)
    error_message: str | None = Field(default=None, max_length=500)

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
    def validate_page(self) -> PlatformSearchPage:
        if len(self.items) > self.requested_page_size:
            raise ValueError("search page exceeds requested_page_size")
        if any(item.platform is not self.platform for item in self.items):
            raise ValueError("search item crosses platform boundary")
        item_ids = [(item.item_type, item.item_id) for item in self.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("search item ids must be unique within a page")
        expected_type = PlatformSearchItemType.ACCOUNT if self.target is PlatformSearchTarget.ACCOUNTS else PlatformSearchItemType.POST
        if any(item.item_type is not expected_type for item in self.items):
            raise ValueError("search item type does not match target")
        if self.status is PlatformSearchStatus.SUCCESS and self.error_code is not None:
            raise ValueError("successful search page cannot carry error_code")
        if self.status not in {PlatformSearchStatus.SUCCESS, PlatformSearchStatus.PARTIAL} and self.items:
            raise ValueError("failed search page cannot carry items")
        return self


class CrossPlatformSearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    target: PlatformSearchTarget
    platforms: tuple[SearchPlatform, ...] = SUPPORTED_SEARCH_PLATFORMS
    page_size_per_platform: int = Field(default=30, ge=1, le=100)
    cursors: dict[SearchPlatform, str] = Field(default_factory=dict)
    session_refs: dict[SearchPlatform, str] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_platforms(self) -> CrossPlatformSearchRequest:
        if not self.platforms:
            raise ValueError("at least one platform is required")
        if len(set(self.platforms)) != len(self.platforms):
            raise ValueError("platforms must be unique")
        if set(self.cursors).difference(self.platforms):
            raise ValueError("cursor references a platform outside this search")
        if set(self.session_refs).difference(self.platforms):
            raise ValueError("session_ref references a platform outside this search")
        return self


class CrossPlatformSearchResult(StrictModel):
    query: str
    target: PlatformSearchTarget
    pages: tuple[PlatformSearchPage, ...]
    started_at: datetime
    completed_at: datetime

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime, info) -> datetime:
        return _aware(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_result(self) -> CrossPlatformSearchResult:
        platforms = [page.platform for page in self.pages]
        if len(set(platforms)) != len(platforms):
            raise ValueError("cross-platform result contains duplicate platforms")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self

    def page_for(self, platform: SearchPlatform) -> PlatformSearchPage:
        for page in self.pages:
            if page.platform is platform:
                return page
        raise KeyError(platform)


class PlatformSearchAdapter(Protocol):
    def search(
        self,
        *,
        request: PlatformSearchRequest,
        credentials: LocalBrowserCredentials | None,
    ) -> object: ...


def _error_page(
    request: PlatformSearchRequest,
    *,
    status: PlatformSearchStatus,
    error_code: str,
    error_message: str,
) -> PlatformSearchPage:
    return PlatformSearchPage(
        platform=request.platform,
        target=request.target,
        query=request.query,
        requested_page_size=request.page_size,
        status=status,
        source=PlatformSearchSource.UNKNOWN,
        capability_version="unavailable-v1",
        authenticated=False,
        captured_at=datetime.now(UTC),
        error_code=error_code,
        error_message=error_message,
    )


async def _await_if_needed(value: object) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def collect_platform_search(
    request: PlatformSearchRequest,
    *,
    adapter: PlatformSearchAdapter,
    credential_provider: LocalBrowserCredentialProvider | None = None,
) -> PlatformSearchPage:
    credentials: LocalBrowserCredentials | None = None
    if request.session_ref is not None:
        if credential_provider is None:
            return _error_page(
                request,
                status=PlatformSearchStatus.NEEDS_LOGIN,
                error_code="session_not_connected",
                error_message="The selected local browser session is not connected.",
            )
        try:
            credentials = credential_provider.load(request.platform, request.session_ref)
        except LocalBrowserCredentialNotFound:
            return _error_page(
                request,
                status=PlatformSearchStatus.NEEDS_LOGIN,
                error_code="session_not_connected",
                error_message="The selected local browser session is not connected.",
            )
        except InvalidLocalBrowserCredential:
            return _error_page(
                request,
                status=PlatformSearchStatus.FAILED,
                error_code="invalid_local_session",
                error_message="The selected local browser session could not be loaded.",
            )

    try:
        raw = await _await_if_needed(adapter.search(request=request, credentials=credentials))
    except Exception:
        return _error_page(
            request,
            status=PlatformSearchStatus.FAILED,
            error_code="collector_failed",
            error_message="The platform collector failed.",
        )

    try:
        page = PlatformSearchPage.model_validate(raw)
    except (ValidationError, TypeError, ValueError):
        return _error_page(
            request,
            status=PlatformSearchStatus.SCHEMA_DRIFT,
            error_code="collector_schema_drift",
            error_message="The platform response no longer matches the collector schema.",
        )

    if page.platform is not request.platform or page.target is not request.target or page.query != request.query or page.requested_page_size != request.page_size:
        return _error_page(
            request,
            status=PlatformSearchStatus.SCHEMA_DRIFT,
            error_code="collector_request_mismatch",
            error_message="The platform collector returned data for another request.",
        )
    return page


async def search_across_platforms(
    request: CrossPlatformSearchRequest,
    *,
    adapters: Mapping[SearchPlatform, PlatformSearchAdapter],
    credential_provider: LocalBrowserCredentialProvider | None = None,
) -> CrossPlatformSearchResult:
    started_at = datetime.now(UTC)

    async def run_one(platform: SearchPlatform) -> PlatformSearchPage:
        platform_request = PlatformSearchRequest(
            platform=platform,
            target=request.target,
            query=request.query,
            page_size=request.page_size_per_platform,
            cursor=request.cursors.get(platform),
            session_ref=request.session_refs.get(platform),
        )
        adapter = adapters.get(platform)
        if adapter is None:
            return _error_page(
                platform_request,
                status=PlatformSearchStatus.UNAVAILABLE,
                error_code="adapter_unavailable",
                error_message="No collector adapter is installed for this platform.",
            )
        return await collect_platform_search(
            platform_request,
            adapter=adapter,
            credential_provider=credential_provider,
        )

    pages = tuple(await asyncio.gather(*(run_one(platform) for platform in request.platforms)))
    return CrossPlatformSearchResult(
        query=request.query,
        target=request.target,
        pages=pages,
        started_at=started_at,
        completed_at=datetime.now(UTC),
    )


__all__ = [
    "SUPPORTED_SEARCH_PLATFORMS",
    "CrossPlatformSearchRequest",
    "CrossPlatformSearchResult",
    "PlatformSearchAdapter",
    "PlatformSearchItem",
    "PlatformSearchItemType",
    "PlatformSearchPage",
    "PlatformSearchRequest",
    "PlatformSearchSource",
    "PlatformSearchStatus",
    "PlatformSearchTarget",
    "SearchPlatform",
    "collect_platform_search",
    "search_across_platforms",
]
