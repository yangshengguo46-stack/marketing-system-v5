from __future__ import annotations

import asyncio
import inspect
import os
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from .audience_collection import (
    AudienceCollectionRequest,
    AudienceCollectionSnapshot,
    AudienceCollectionSource,
    AudienceCollectionStatus,
    AudienceDataset,
    AudienceDatasetCoverage,
    AudienceDatasetStatus,
)
from .audience_evidence import (
    AudienceInteractionKind,
    AudienceInteractionObservation,
)
from .audience_snapshot_adapter import SourceSnapshotAudienceAdapter
from .contracts import StrictModel, canonical_sha256
from .local_browser_credentials import LocalBrowserCredentials
from .platform_search import SearchPlatform
from .source_snapshot import AccountSourceSnapshot, PostListObservation


class DouyinCommentPayloadError(RuntimeError):
    """A stable error for an unusable first-party comment response."""


def _aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int | float) and value >= 0:
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


class RawDouyinComment(StrictModel):
    """Process-local comment row; raw_actor_id must never be persisted."""

    comment_id: str = Field(min_length=1, max_length=500)
    post_id: str = Field(min_length=1, max_length=500)
    raw_actor_id: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=8_000)
    occurred_at: datetime | None = None
    visible_like_count: int = Field(default=0, ge=0)
    visible_reply_count: int = Field(default=0, ge=0)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _aware(value, field_name="occurred_at")


class DouyinCommentCapture(StrictModel):
    captured_at: datetime
    attempted_post_ids: tuple[str, ...]
    comments: tuple[RawDouyinComment, ...] = Field(default_factory=tuple)
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _aware(value, field_name="captured_at")

    @field_validator("attempted_post_ids")
    @classmethod
    def validate_attempted_post_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(set(value)) != len(value) or any(not item for item in value):
            raise ValueError("attempted post ids must be non-empty and unique")
        return value

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 1_200 for item in value):
            raise ValueError("limitations must be non-empty and at most 1200 characters")
        return value


def parse_douyin_comment_payload(
    payload: object,
    *,
    post_id: str,
) -> tuple[RawDouyinComment, ...]:
    """Parse one bounded first-party response without retaining its raw envelope."""

    if not isinstance(payload, Mapping) or payload.get("status_code") not in {None, 0}:
        raise DouyinCommentPayloadError("Douyin comment response schema was not usable.")
    raw_comments = payload.get("comments")
    if raw_comments is None:
        return ()
    if not isinstance(raw_comments, list):
        raise DouyinCommentPayloadError("Douyin comment response schema changed.")

    comments: list[RawDouyinComment] = []
    for row in raw_comments:
        if not isinstance(row, Mapping):
            raise DouyinCommentPayloadError("Douyin comment response schema changed.")
        row_post_id = str(row.get("aweme_id") or post_id).strip()
        if row_post_id != post_id:
            raise DouyinCommentPayloadError("Douyin comment response contained another post.")
        user = row.get("user")
        if not isinstance(user, Mapping):
            continue
        comment_id = str(row.get("cid") or row.get("comment_id") or "").strip()
        actor_id = str(user.get("sec_uid") or user.get("uid") or "").strip()
        text = str(row.get("text") or "").strip()
        if not comment_id or not actor_id or not text:
            continue
        comments.append(
            RawDouyinComment(
                comment_id=comment_id,
                post_id=post_id,
                raw_actor_id=actor_id,
                text=text[:8_000],
                occurred_at=_timestamp(row.get("create_time")),
                visible_like_count=_non_negative_int(row.get("digg_count")),
                visible_reply_count=_non_negative_int(row.get("reply_comment_total") or row.get("reply_comment_count")),
            )
        )
    return tuple(comments)


def _post_id_from_url(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().strip(".")
    if host != "douyin.com" and not host.endswith(".douyin.com"):
        raise ValueError("Douyin audience runner accepts only Douyin post URLs")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2 or parts[0] != "video" or not parts[1]:
        raise ValueError("Douyin audience runner requires a canonical post URL")
    return parts[1]


class DouyinCommentRunner(Protocol):
    def capture(
        self,
        *,
        post_urls: Sequence[str],
        storage_state: Mapping[str, object],
        max_interactions: int,
    ) -> object: ...


async def _trigger_comment_loading(page: Any) -> bool:
    selectors = (
        '[data-e2e="feed-comment-icon"]',
        '[data-e2e="comment-icon"]',
        '[data-e2e="browse-comment"]',
        'button:has-text("评论")',
        '[aria-label*="评论"]',
        "text=评论",
    )
    for attempt in range(20):
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=3_000)
                    return True
            except Exception:
                continue
        if attempt < 19:
            await page.wait_for_timeout(500)
    await page.mouse.wheel(0, 900)
    return False


class LocalPlaywrightDouyinCommentRunner:
    """Collect bounded visible interactions from an authenticated local browser."""

    def __init__(
        self,
        *,
        headless: bool = False,
        navigation_timeout_ms: int = 60_000,
        settle_ms: int = 3_000,
    ) -> None:
        self._headless = headless
        self._navigation_timeout_ms = navigation_timeout_ms
        self._settle_ms = settle_ms

    async def capture(
        self,
        *,
        post_urls: Sequence[str],
        storage_state: Mapping[str, object],
        max_interactions: int,
    ) -> DouyinCommentCapture:
        if not post_urls:
            raise ValueError("at least one Douyin post URL is required")
        if max_interactions <= 0:
            raise ValueError("max_interactions must be positive")
        post_ids = tuple(_post_id_from_url(url) for url in post_urls)
        if len(set(post_ids)) != len(post_ids):
            raise ValueError("Douyin post URLs must be unique")
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright browser support is not installed") from exc

        captured_at = datetime.now(UTC)
        comments: list[RawDouyinComment] = []
        seen_ids: set[str] = set()
        limitations: list[str] = []
        attempted_post_ids: list[str] = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self._headless)
            try:
                context = await browser.new_context(storage_state=dict(storage_state))
                page = await context.new_page()
                for post_url, post_id in zip(post_urls, post_ids, strict=True):
                    if len(comments) >= max_interactions:
                        limitations.append("The interaction cap was reached before every selected post was visited.")
                        break
                    attempted_post_ids.append(post_id)
                    payloads: list[object] = []
                    pending: set[asyncio.Task[None]] = set()
                    response_seen = asyncio.Event()

                    async def read_response(response: object) -> None:
                        url = str(getattr(response, "url", ""))
                        if "/aweme/v1/web/comment/list/" not in url:
                            return
                        try:
                            headers = await response.all_headers()
                            content_type = str(headers.get("content-type", "")).lower()
                            if "json" not in content_type:
                                return
                            payloads.append(await response.json())
                            response_seen.set()
                        except Exception:
                            return

                    def on_response(response: object) -> None:
                        task = asyncio.create_task(read_response(response))
                        pending.add(task)
                        task.add_done_callback(pending.discard)

                    page.on("response", on_response)
                    try:
                        await page.goto(
                            post_url,
                            wait_until="domcontentloaded",
                            timeout=self._navigation_timeout_ms,
                        )
                        await page.wait_for_timeout(self._settle_ms)
                        await _trigger_comment_loading(page)
                        try:
                            await asyncio.wait_for(response_seen.wait(), timeout=10)
                            await page.wait_for_timeout(750)
                        except TimeoutError:
                            pass
                        if pending:
                            await asyncio.gather(*tuple(pending), return_exceptions=True)
                    finally:
                        page.remove_listener("response", on_response)
                    parsed_any = False
                    for payload in payloads:
                        parsed = parse_douyin_comment_payload(payload, post_id=post_id)
                        parsed_any = parsed_any or bool(parsed)
                        for comment in parsed:
                            if comment.comment_id in seen_ids:
                                continue
                            seen_ids.add(comment.comment_id)
                            comments.append(comment)
                            if len(comments) >= max_interactions:
                                break
                        if len(comments) >= max_interactions:
                            break
                    if not parsed_any:
                        limitations.append(f"No usable visible interaction rows were captured for post {post_id}.")
            finally:
                await browser.close()
        return DouyinCommentCapture(
            captured_at=captured_at,
            attempted_post_ids=tuple(attempted_post_ids),
            comments=tuple(comments),
            limitations=tuple(limitations),
        )


@dataclass(frozen=True, slots=True)
class DouyinAuthenticatedAudienceAdapter:
    source: AccountSourceSnapshot
    runner: DouyinCommentRunner = field(default_factory=LocalPlaywrightDouyinCommentRunner)
    local_actor_salt: str = field(repr=False, default="")
    post_ids: tuple[str, ...] | None = None

    capability_version = "douyin-authenticated-audience-v1"

    def __post_init__(self) -> None:
        if self.source.profile.platform != SearchPlatform.DOUYIN.value:
            raise ValueError("Douyin audience adapter requires a Douyin source snapshot")
        if not self.local_actor_salt:
            raise ValueError("local_actor_salt is required")
        known_ids = {post.post_id for post in self.source.posts}
        selected = self.post_ids or tuple(post.post_id for post in self.source.posts)
        if not selected or len(set(selected)) != len(selected):
            raise ValueError("selected post ids must be non-empty and unique")
        if not set(selected).issubset(known_ids):
            raise ValueError("selected post id is outside the source snapshot")
        object.__setattr__(self, "post_ids", selected)

    async def collect(
        self,
        *,
        request: AudienceCollectionRequest,
        credentials: LocalBrowserCredentials | None,
    ) -> AudienceCollectionSnapshot:
        source_sha256 = canonical_sha256(self.source.model_dump(mode="json"))
        if request.platform is not SearchPlatform.DOUYIN:
            raise ValueError("audience request is not for Douyin")
        if request.account_id != self.source.profile.account_id:
            raise ValueError("audience request does not match source account")
        if request.source_account_snapshot_sha256 != source_sha256:
            raise ValueError("audience request does not match source snapshot")
        baseline = SourceSnapshotAudienceAdapter(source=self.source).collect(
            request=request,
            credentials=None,
        )
        if AudienceDataset.CONTENT_INTERACTIONS not in request.datasets:
            return baseline
        if credentials is None:
            raise ValueError("authenticated Douyin audience collection requires local login state")

        posts_by_id: dict[str, PostListObservation] = {post.post_id: post for post in self.source.posts}
        selected_posts = tuple(posts_by_id[post_id] for post_id in self.post_ids or ())
        raw_capture = self.runner.capture(
            post_urls=tuple(post.canonical_url for post in selected_posts),
            storage_state=credentials.playwright_storage_state(),
            max_interactions=request.max_interactions,
        )
        if inspect.isawaitable(raw_capture):
            raw_capture = await raw_capture
        capture = DouyinCommentCapture.model_validate(raw_capture)
        expected_ids = tuple(post.post_id for post in selected_posts)
        attempted_ids = capture.attempted_post_ids
        if attempted_ids != expected_ids[: len(attempted_ids)]:
            raise ValueError("audience runner changed the requested post set")

        interactions: list[AudienceInteractionObservation] = []
        for raw in capture.comments:
            post = posts_by_id.get(raw.post_id)
            if post is None or raw.post_id not in attempted_ids:
                raise ValueError("audience response contains a post outside the source snapshot")
            interaction_key = canonical_sha256(
                {
                    "platform": "douyin",
                    "account_id": request.account_id,
                    "post_id": raw.post_id,
                    "comment_id": raw.comment_id,
                }
            )
            interactions.append(
                AudienceInteractionObservation.from_raw_actor(
                    interaction_id=f"douyin-comment-{interaction_key}",
                    platform="douyin",
                    account_id=request.account_id,
                    item_id=raw.post_id,
                    item_text=post.caption or f"Douyin post {post.post_id}",
                    kind=AudienceInteractionKind.COMMENT,
                    raw_actor_id=raw.raw_actor_id,
                    local_salt=self.local_actor_salt,
                    text=raw.text,
                    public_metrics={
                        "likes": raw.visible_like_count,
                        "replies": raw.visible_reply_count,
                    },
                    occurred_at=raw.occurred_at,
                    captured_at=capture.captured_at,
                    evidence_ref=(f"platform://douyin/post/{raw.post_id}/comment/{raw.comment_id}"),
                )
            )

        metrics = baseline.metrics
        metric_counts = {dataset: sum(metric.dataset is dataset for metric in metrics) for dataset in request.datasets}
        coverage: list[AudienceDatasetCoverage] = []
        for dataset in request.datasets:
            if dataset is AudienceDataset.CONTENT_INTERACTIONS:
                record_count = metric_counts[dataset] + len(interactions)
                coverage.append(
                    AudienceDatasetCoverage(
                        dataset=dataset,
                        status=(AudienceDatasetStatus.PARTIAL if record_count else AudienceDatasetStatus.UNAVAILABLE),
                        record_count=record_count,
                        source=AudienceCollectionSource.AUTHENTICATED_PLATFORM,
                        limitations=("Only bounded visible audience responses from selected account posts were observed; this is not a follower census.",),
                    )
                )
            elif metric_counts[dataset]:
                coverage.append(
                    AudienceDatasetCoverage(
                        dataset=dataset,
                        status=AudienceDatasetStatus.COLLECTED,
                        record_count=metric_counts[dataset],
                        source=AudienceCollectionSource.PUBLIC_PLATFORM,
                    )
                )
            else:
                coverage.append(
                    AudienceDatasetCoverage(
                        dataset=dataset,
                        status=AudienceDatasetStatus.UNAVAILABLE,
                        record_count=0,
                        source=AudienceCollectionSource.AUTHENTICATED_PLATFORM,
                        limitations=("This dataset was not present in the bounded authenticated observation.",),
                    )
                )
        has_records = bool(metrics or interactions)
        return AudienceCollectionSnapshot(
            platform=request.platform,
            account_id=request.account_id,
            source_account_snapshot_sha256=source_sha256,
            requested_datasets=request.datasets,
            status=(AudienceCollectionStatus.PARTIAL if has_records else AudienceCollectionStatus.UNAVAILABLE),
            source=AudienceCollectionSource.AUTHENTICATED_PLATFORM,
            capability_version=self.capability_version,
            authenticated=True,
            coverage=tuple(coverage),
            metrics=metrics,
            interactions=tuple(interactions),
            captured_at=capture.captured_at,
            limitations=tuple(
                dict.fromkeys(
                    (
                        "Visible audience interactions are a bounded response sample, not verified follower demographics.",
                        *capture.limitations,
                    )
                )
            ),
        )


def load_or_create_local_actor_salt(path: Path) -> str:
    """Keep one stable pseudonym salt in an untracked, owner-only local file."""

    resolved = path.expanduser().resolve()
    if resolved.is_file():
        value = resolved.read_text(encoding="utf-8").strip()
        if len(value) < 32:
            raise ValueError("local actor salt is invalid")
        return value
    resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(resolved.parent, 0o700)
    value = secrets.token_hex(32)
    descriptor = os.open(resolved, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, value.encode("ascii"))
    finally:
        os.close(descriptor)
    return value


__all__ = [
    "DouyinAuthenticatedAudienceAdapter",
    "DouyinCommentCapture",
    "DouyinCommentPayloadError",
    "LocalPlaywrightDouyinCommentRunner",
    "RawDouyinComment",
    "load_or_create_local_actor_salt",
    "parse_douyin_comment_payload",
]
