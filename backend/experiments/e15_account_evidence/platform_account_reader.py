from __future__ import annotations

from collections import Counter
from urllib.parse import quote, urljoin, urlsplit

import httpx

from .account_link_collection import StructuredAccountObservation
from .local_browser_credentials import LocalBrowserCredentialProvider
from .platform_search import (
    PlatformSearchAdapter,
    PlatformSearchItem,
    PlatformSearchRequest,
    PlatformSearchStatus,
    PlatformSearchTarget,
    SearchPlatform,
    collect_platform_search,
)
from .source_snapshot import AccountProfileObservation, PostListObservation


class PlatformAccountReadError(RuntimeError):
    """A stable account-read failure that never includes browser credentials."""


_PLATFORM_HOSTS: dict[SearchPlatform, tuple[str, ...]] = {
    SearchPlatform.DOUYIN: ("douyin.com", "iesdouyin.com"),
    SearchPlatform.XIAOHONGSHU: ("xiaohongshu.com",),
    SearchPlatform.KUAISHOU: ("kuaishou.com", "gifshow.com"),
    SearchPlatform.BILIBILI: ("bilibili.com",),
    SearchPlatform.TIKTOK: ("tiktok.com",),
    SearchPlatform.WECHAT_CHANNELS: (),
}


def _platform_host(platform: SearchPlatform, value: str) -> bool:
    host = (urlsplit(value).hostname or "").lower().strip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in _PLATFORM_HOSTS[platform])


def _canonical_douyin_profile(value: str) -> str | None:
    parts = [part for part in urlsplit(value).path.split("/") if part]
    if len(parts) >= 2 and parts[-2] == "user" and parts[-1]:
        return f"https://www.douyin.com/user/{quote(parts[-1], safe='')}"
    return None


async def resolve_platform_account_url(
    *,
    platform: SearchPlatform,
    requested_url: str,
    transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
) -> str:
    requested_url = _clean_requested_url(requested_url)
    if platform is not SearchPlatform.DOUYIN:
        return requested_url
    if not _platform_host(platform, requested_url):
        raise PlatformAccountReadError("Account URL belongs to another platform.")
    canonical = _canonical_douyin_profile(requested_url)
    if canonical is not None:
        return canonical

    current = requested_url
    async with httpx.AsyncClient(
        transport=transport,
        follow_redirects=False,
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as client:
        for _ in range(6):
            response = await client.get(current)
            if response.status_code not in {301, 302, 303, 307, 308}:
                break
            location = response.headers.get("location")
            if not location:
                break
            current = urljoin(current, location)
            if not _platform_host(platform, current):
                raise PlatformAccountReadError("Account short link redirected outside the selected platform.")
            canonical = _canonical_douyin_profile(current)
            if canonical is not None:
                return canonical
    raise PlatformAccountReadError("Account short link did not resolve to a stable platform profile.")


def _clean_requested_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("requested_url must be an absolute http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("requested_url must not contain credentials")
    return parsed._replace(fragment="").geturl()


def _single_author(items: tuple[PlatformSearchItem, ...]) -> tuple[str, str | None]:
    if any(not item.author_id for item in items):
        raise PlatformAccountReadError("Account post collection returned no stable account identity; snapshot was not created.")
    author_ids = {item.author_id for item in items if item.author_id}
    if len(author_ids) != 1:
        reason = "multiple accounts" if len(author_ids) > 1 else "no stable account identity"
        raise PlatformAccountReadError(f"Account post collection returned {reason}; snapshot was not created.")
    account_id = next(iter(author_ids))
    names = Counter(item.author_name.strip() for item in items if item.author_name and item.author_id == account_id and item.author_name.strip())
    display_name = names.most_common(1)[0][0] if names else None
    return account_id, display_name


def _consistent_author_field(
    items: tuple[PlatformSearchItem, ...],
    field_name: str,
    *,
    limitation_name: str,
) -> tuple[object | None, tuple[str, ...]]:
    values = {value for item in items if (value := getattr(item, field_name)) is not None}
    if len(values) == 1:
        return next(iter(values)), ()
    if len(values) > 1:
        return None, (f"Conflicting author {limitation_name} was omitted from the account snapshot.",)
    return None, ()


def _consistent_author_metrics(
    items: tuple[PlatformSearchItem, ...],
) -> tuple[dict[str, int | float], tuple[str, ...]]:
    values_by_name: dict[str, set[int | float]] = {}
    for item in items:
        for name, value in item.author_public_metrics.items():
            values_by_name.setdefault(name, set()).add(value)
    metrics: dict[str, int | float] = {}
    limitations: list[str] = []
    for name, values in sorted(values_by_name.items()):
        if len(values) == 1:
            metrics[name] = next(iter(values))
        else:
            limitations.append(f"Conflicting author metric {name!r} was omitted from the account snapshot.")
    return metrics, tuple(limitations)


class PlatformAccountReader:
    """Adapt a bounded platform account page into E15's snapshot input contract."""

    def __init__(
        self,
        *,
        platform: SearchPlatform,
        adapter: PlatformSearchAdapter,
        credential_provider: LocalBrowserCredentialProvider | None = None,
        session_ref: str | None = None,
    ) -> None:
        self.platform = platform
        self._adapter = adapter
        self._credential_provider = credential_provider
        self._session_ref = session_ref

    async def __call__(
        self,
        *,
        requested_url: str,
        max_posts: int,
    ) -> StructuredAccountObservation:
        requested_url = _clean_requested_url(requested_url)
        collection_url = await resolve_platform_account_url(
            platform=self.platform,
            requested_url=requested_url,
        )
        page = await collect_platform_search(
            PlatformSearchRequest(
                platform=self.platform,
                target=PlatformSearchTarget.ACCOUNT_POSTS,
                query=collection_url,
                page_size=max_posts,
                session_ref=self._session_ref,
            ),
            adapter=self._adapter,
            credential_provider=self._credential_provider,
        )
        if page.status not in {
            PlatformSearchStatus.SUCCESS,
            PlatformSearchStatus.PARTIAL,
        }:
            raise PlatformAccountReadError(f"Account post collection ended with status {page.status.value}.")
        if not page.items:
            raise PlatformAccountReadError("Account post collection returned no stable posts; snapshot was not created.")

        account_id, display_name = _single_author(page.items)
        author_metrics, author_metric_limitations = _consistent_author_metrics(page.items)
        author_bio, author_bio_limitations = _consistent_author_field(
            page.items,
            "author_bio",
            limitation_name="bio",
        )
        author_verification, author_verification_limitations = _consistent_author_field(
            page.items,
            "author_verification",
            limitation_name="verification",
        )
        visible_work_count, work_count_limitations = _consistent_author_field(
            page.items,
            "author_visible_work_count",
            limitation_name="visible work count",
        )
        canonical_profile_url = _canonical_profile_url(
            platform=self.platform,
            account_id=account_id,
            requested_url=requested_url,
        )
        posts = tuple(
            PostListObservation(
                post_id=item.item_id,
                canonical_url=item.canonical_url,
                caption=item.title or item.description,
                published_at=item.published_at,
                captured_at=item.captured_at,
                public_metrics=item.public_metrics,
            )
            for item in page.items
        )
        limitations = list(page.limitations)
        limitations.extend(author_metric_limitations)
        limitations.extend(author_bio_limitations)
        limitations.extend(author_verification_limitations)
        limitations.extend(work_count_limitations)
        limitations.append("Profile identity was derived from the consistent author fields in the collected post list.")
        if page.status is PlatformSearchStatus.PARTIAL:
            limitations.append("The platform returned only a partial account post list.")
        return StructuredAccountObservation(
            profile=AccountProfileObservation(
                platform=self.platform.value,
                account_id=account_id,
                canonical_url=canonical_profile_url,
                display_name=display_name,
                bio=author_bio,
                verification=author_verification,
                visible_work_count=visible_work_count,
                public_metrics=author_metrics,
                captured_at=page.captured_at,
            ),
            posts=posts,
            final_url=canonical_profile_url,
            sample_basis=(f"Bounded account posts observed by the local platform adapter; requested at most {max_posts} posts."),
            captured_at=page.captured_at,
            limitations=tuple(limitations),
        )


def _canonical_profile_url(
    *,
    platform: SearchPlatform,
    account_id: str,
    requested_url: str,
) -> str:
    if platform is SearchPlatform.DOUYIN:
        return f"https://www.douyin.com/user/{account_id}"
    if platform is SearchPlatform.XIAOHONGSHU:
        return f"https://www.xiaohongshu.com/user/profile/{account_id}"
    if platform is SearchPlatform.KUAISHOU:
        return f"https://www.kuaishou.com/profile/{account_id}"
    if platform is SearchPlatform.BILIBILI:
        return f"https://space.bilibili.com/{account_id}"
    if platform is SearchPlatform.TIKTOK:
        parsed = urlsplit(requested_url)
        if parsed.path.startswith("/@"):
            return parsed._replace(query="", fragment="").geturl().rstrip("/")
        return f"https://www.tiktok.com/@{account_id}"
    if platform is SearchPlatform.WECHAT_CHANNELS:
        return requested_url
    raise PlatformAccountReadError("Unsupported account platform.")


__all__ = [
    "PlatformAccountReadError",
    "PlatformAccountReader",
    "resolve_platform_account_url",
]
