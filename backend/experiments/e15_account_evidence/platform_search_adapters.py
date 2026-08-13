from __future__ import annotations

import asyncio
import html
import inspect
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from urllib.parse import quote, quote_plus, urljoin, urlsplit

from .local_browser_credentials import LocalBrowserCredentials
from .platform_search import (
    PlatformSearchItem,
    PlatformSearchItemType,
    PlatformSearchPage,
    PlatformSearchRequest,
    PlatformSearchSource,
    PlatformSearchStatus,
    PlatformSearchTarget,
    SearchPlatform,
)


class BrowserSearchPageState(StrEnum):
    READY = "ready"
    NEEDS_LOGIN = "needs_login"
    RESTRICTED = "restricted"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class BrowserLinkObservation:
    href: str
    text: str = ""


@dataclass(frozen=True, slots=True)
class BrowserSearchCapture:
    """Ephemeral browser capture passed only from the runner to the adapter."""

    captured_at: datetime
    final_url: str
    page_state: BrowserSearchPageState
    response_payloads: tuple[object, ...] = field(default_factory=tuple, repr=False)
    visible_links: tuple[BrowserLinkObservation, ...] = field(default_factory=tuple, repr=False)
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __repr__(self) -> str:
        return (
            "BrowserSearchCapture("
            f"captured_at={self.captured_at!r}, final_url={self.final_url!r}, "
            f"page_state={self.page_state!r}, "
            f"response_payload_count={len(self.response_payloads)}, "
            f"visible_link_count={len(self.visible_links)}, "
            f"limitations={self.limitations!r})"
        )


class BrowserSearchRunner(Protocol):
    def capture(
        self,
        *,
        url: str,
        platform: SearchPlatform,
        target: PlatformSearchTarget,
        page_size: int,
        storage_state: Mapping[str, object] | None,
    ) -> BrowserSearchCapture | Awaitable[BrowserSearchCapture]: ...


_WEB_PLATFORMS = frozenset(
    {
        SearchPlatform.DOUYIN,
        SearchPlatform.XIAOHONGSHU,
        SearchPlatform.KUAISHOU,
        SearchPlatform.BILIBILI,
        SearchPlatform.TIKTOK,
    }
)

_PLATFORM_HOSTS: dict[SearchPlatform, tuple[str, ...]] = {
    SearchPlatform.DOUYIN: ("douyin.com", "iesdouyin.com"),
    SearchPlatform.XIAOHONGSHU: ("xiaohongshu.com",),
    SearchPlatform.KUAISHOU: ("kuaishou.com", "gifshow.com"),
    SearchPlatform.BILIBILI: ("bilibili.com",),
    SearchPlatform.TIKTOK: ("tiktok.com",),
}

_BASE_URLS: dict[SearchPlatform, str] = {
    SearchPlatform.DOUYIN: "https://www.douyin.com",
    SearchPlatform.XIAOHONGSHU: "https://www.xiaohongshu.com",
    SearchPlatform.KUAISHOU: "https://www.kuaishou.com",
    SearchPlatform.BILIBILI: "https://www.bilibili.com",
    SearchPlatform.TIKTOK: "https://www.tiktok.com",
}


def _host_matches(host: str, domains: Sequence[str]) -> bool:
    normalized = host.lower().strip().lstrip(".")
    return any(normalized == domain or normalized.endswith(f".{domain}") for domain in domains)


def _absolute_http_url(value: object, *, base: str | None = None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith("//"):
        raw = f"https:{raw}"
    elif base is not None:
        raw = urljoin(base, raw)
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    return raw


def _text(value: object, *, limit: int) -> str | None:
    if value is None:
        return None
    plain = re.sub(r"<[^>]+>", "", html.unescape(str(value)))
    normalized = re.sub(r"\s+", " ", plain).strip()
    return normalized[:limit] or None


def _number(value: object) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value if value >= 0 else None
    raw = str(value).strip().replace(",", "").replace("，", "")
    if not raw:
        return None
    multiplier = 1
    suffixes = {
        "万": 10_000,
        "w": 10_000,
        "W": 10_000,
        "千": 1_000,
        "k": 1_000,
        "K": 1_000,
        "m": 1_000_000,
        "M": 1_000_000,
    }
    suffix = raw[-1]
    if suffix in suffixes:
        multiplier = suffixes[suffix]
        raw = raw[:-1]
    match = re.search(r"\d+(?:\.\d+)?", raw)
    if match is None:
        return None
    number = float(match.group(0)) * multiplier
    return int(number) if number.is_integer() else number


def _timestamp(value: object) -> datetime | None:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    if numeric > 10_000_000_000:
        numeric /= 1_000
    try:
        return datetime.fromtimestamp(numeric, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _metrics(source: object, aliases: Mapping[str, Sequence[str]]) -> dict[str, int | float]:
    if not isinstance(source, Mapping):
        return {}
    result: dict[str, int | float] = {}
    for normalized, names in aliases.items():
        for name in names:
            metric = _number(source.get(name))
            if metric is not None:
                result[normalized] = metric
                break
    return result


def _walk_dicts(value: object):
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            yield from _walk_dicts(child)


def _thumbnail(value: object) -> str | None:
    if isinstance(value, str):
        return _absolute_http_url(value)
    if not isinstance(value, Mapping):
        return None
    for key in ("url", "url_default", "url_list", "urlList"):
        candidate = value.get(key)
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
            candidate = next(iter(candidate), None)
        url = _absolute_http_url(candidate)
        if url is not None:
            return url
    return None


def _douyin_items(
    *,
    payload: object,
    target: PlatformSearchTarget,
    captured_at: datetime,
) -> list[PlatformSearchItem]:
    items: list[PlatformSearchItem] = []
    if target is PlatformSearchTarget.ACCOUNTS:
        for node in _walk_dicts(payload):
            user = node.get("user_info")
            if not isinstance(user, Mapping):
                continue
            account_id = str(user.get("sec_uid") or user.get("uid") or "").strip()
            if not account_id:
                continue
            items.append(
                PlatformSearchItem(
                    platform=SearchPlatform.DOUYIN,
                    item_type=PlatformSearchItemType.ACCOUNT,
                    item_id=account_id,
                    canonical_url=(f"https://www.douyin.com/user/{quote(account_id, safe='')}"),
                    title=_text(user.get("nickname"), limit=2_000),
                    description=_text(user.get("signature"), limit=8_000),
                    author_id=str(user.get("uid") or account_id),
                    author_name=_text(user.get("nickname"), limit=500),
                    captured_at=captured_at,
                    public_metrics=_metrics(
                        user,
                        {
                            "followers": ("follower_count", "fans_count"),
                            "following": ("following_count",),
                            "likes_received": ("total_favorited",),
                        },
                    ),
                    thumbnail_url=_thumbnail(user.get("avatar_larger")),
                )
            )
        return items

    for node in _walk_dicts(payload):
        aweme = node.get("aweme_info")
        if not isinstance(aweme, Mapping):
            continue
        item_id = str(aweme.get("aweme_id") or aweme.get("id") or "").strip()
        if not item_id:
            continue
        author = aweme.get("author") if isinstance(aweme.get("author"), Mapping) else {}
        stats = aweme.get("statistics") or aweme.get("stats") or {}
        video = aweme.get("video") if isinstance(aweme.get("video"), Mapping) else {}
        items.append(
            PlatformSearchItem(
                platform=SearchPlatform.DOUYIN,
                item_type=PlatformSearchItemType.POST,
                item_id=item_id,
                canonical_url=f"https://www.douyin.com/video/{quote(item_id, safe='')}",
                title=_text(aweme.get("desc"), limit=2_000),
                description=_text(aweme.get("desc"), limit=8_000),
                author_id=str(author.get("sec_uid") or author.get("uid") or "") or None,
                author_name=_text(author.get("nickname"), limit=500),
                author_public_metrics=_metrics(
                    author,
                    {
                        "followers": ("follower_count", "fans_count"),
                        "following": ("following_count",),
                        "likes_received": ("total_favorited",),
                    },
                ),
                published_at=_timestamp(aweme.get("create_time")),
                captured_at=captured_at,
                public_metrics=_metrics(
                    stats,
                    {
                        "plays": ("play_count",),
                        "likes": ("digg_count",),
                        "comments": ("comment_count",),
                        "shares": ("share_count",),
                        "favorites": ("collect_count",),
                    },
                ),
                thumbnail_url=_thumbnail(video.get("cover") or video.get("origin_cover")),
            )
        )
    return items


def _xiaohongshu_items(
    *,
    payload: object,
    target: PlatformSearchTarget,
    captured_at: datetime,
) -> list[PlatformSearchItem]:
    items: list[PlatformSearchItem] = []
    for node in _walk_dicts(payload):
        if target is PlatformSearchTarget.ACCOUNTS:
            user = node.get("user") or node.get("user_info")
            if not isinstance(user, Mapping):
                continue
            account_id = str(user.get("user_id") or user.get("id") or "").strip()
            if not account_id:
                continue
            items.append(
                PlatformSearchItem(
                    platform=SearchPlatform.XIAOHONGSHU,
                    item_type=PlatformSearchItemType.ACCOUNT,
                    item_id=account_id,
                    canonical_url=(f"https://www.xiaohongshu.com/user/profile/{quote(account_id, safe='')}"),
                    title=_text(user.get("nickname") or user.get("name"), limit=2_000),
                    description=_text(user.get("desc") or user.get("signature"), limit=8_000),
                    author_id=account_id,
                    author_name=_text(user.get("nickname") or user.get("name"), limit=500),
                    captured_at=captured_at,
                    public_metrics=_metrics(
                        user,
                        {"followers": ("fans", "fans_count", "follower_count")},
                    ),
                    thumbnail_url=_thumbnail(user.get("image") or user.get("avatar")),
                )
            )
            continue

        card = node.get("note_card") or node.get("noteCard")
        if not isinstance(card, Mapping):
            continue
        item_id = str(card.get("note_id") or card.get("id") or "").strip()
        if not item_id:
            continue
        user = card.get("user") if isinstance(card.get("user"), Mapping) else {}
        interaction = card.get("interact_info") or card.get("interactInfo") or {}
        cover = card.get("cover") or card.get("image_list") or card.get("imageList")
        if isinstance(cover, Sequence) and not isinstance(cover, (str, bytes, Mapping)):
            cover = next(iter(cover), None)
        items.append(
            PlatformSearchItem(
                platform=SearchPlatform.XIAOHONGSHU,
                item_type=PlatformSearchItemType.POST,
                item_id=item_id,
                canonical_url=(f"https://www.xiaohongshu.com/explore/{quote(item_id, safe='')}"),
                title=_text(card.get("display_title") or card.get("title"), limit=2_000),
                description=_text(card.get("desc"), limit=8_000),
                author_id=str(user.get("user_id") or user.get("id") or "") or None,
                author_name=_text(user.get("nickname") or user.get("name"), limit=500),
                author_public_metrics=_metrics(
                    user,
                    {"followers": ("fans", "fans_count", "follower_count")},
                ),
                published_at=_timestamp(card.get("time") or card.get("create_time")),
                captured_at=captured_at,
                public_metrics=_metrics(
                    interaction,
                    {
                        "likes": ("liked_count", "likedCount"),
                        "comments": ("comment_count", "commentCount"),
                        "favorites": ("collected_count", "collectedCount"),
                        "shares": ("share_count", "shareCount"),
                    },
                ),
                thumbnail_url=_thumbnail(cover),
            )
        )
    return items


def _kuaishou_items(
    *,
    payload: object,
    target: PlatformSearchTarget,
    captured_at: datetime,
) -> list[PlatformSearchItem]:
    items: list[PlatformSearchItem] = []
    for node in _walk_dicts(payload):
        if target is PlatformSearchTarget.ACCOUNTS:
            user = node.get("user") or node.get("author")
            if not isinstance(user, Mapping) or "photo" in node:
                continue
            account_id = str(user.get("id") or user.get("userId") or "").strip()
            if not account_id:
                continue
            items.append(
                PlatformSearchItem(
                    platform=SearchPlatform.KUAISHOU,
                    item_type=PlatformSearchItemType.ACCOUNT,
                    item_id=account_id,
                    canonical_url=f"https://www.kuaishou.com/profile/{quote(account_id, safe='')}",
                    title=_text(user.get("name") or user.get("userName"), limit=2_000),
                    description=_text(user.get("description"), limit=8_000),
                    author_id=account_id,
                    author_name=_text(user.get("name") or user.get("userName"), limit=500),
                    captured_at=captured_at,
                    public_metrics=_metrics(
                        user,
                        {"followers": ("fan", "fansCount", "followerCount")},
                    ),
                    thumbnail_url=_thumbnail(user.get("headerUrl") or user.get("avatar")),
                )
            )
            continue

        photo = node.get("photo")
        if not isinstance(photo, Mapping):
            continue
        item_id = str(photo.get("id") or photo.get("photoId") or "").strip()
        if not item_id:
            continue
        author = node.get("author") if isinstance(node.get("author"), Mapping) else {}
        items.append(
            PlatformSearchItem(
                platform=SearchPlatform.KUAISHOU,
                item_type=PlatformSearchItemType.POST,
                item_id=item_id,
                canonical_url=(f"https://www.kuaishou.com/short-video/{quote(item_id, safe='')}"),
                title=_text(photo.get("caption"), limit=2_000),
                description=_text(photo.get("caption"), limit=8_000),
                author_id=str(author.get("id") or author.get("userId") or "") or None,
                author_name=_text(author.get("name") or author.get("userName"), limit=500),
                author_public_metrics=_metrics(
                    author,
                    {"followers": ("fan", "fansCount", "followerCount")},
                ),
                published_at=_timestamp(photo.get("timestamp") or photo.get("createTime")),
                captured_at=captured_at,
                public_metrics=_metrics(
                    photo,
                    {
                        "plays": ("viewCount", "playCount"),
                        "likes": ("realLikeCount", "likeCount"),
                        "comments": ("commentCount",),
                        "shares": ("shareCount",),
                    },
                ),
                thumbnail_url=_thumbnail(photo.get("coverUrl") or photo.get("coverUrls")),
            )
        )
    return items


def _bilibili_items(
    *,
    payload: object,
    target: PlatformSearchTarget,
    captured_at: datetime,
) -> list[PlatformSearchItem]:
    items: list[PlatformSearchItem] = []
    for node in _walk_dicts(payload):
        if target is PlatformSearchTarget.ACCOUNTS:
            account_id = str(node.get("mid") or "").strip()
            account_name = node.get("uname") or node.get("author")
            if not account_id or not account_name or node.get("bvid"):
                continue
            items.append(
                PlatformSearchItem(
                    platform=SearchPlatform.BILIBILI,
                    item_type=PlatformSearchItemType.ACCOUNT,
                    item_id=account_id,
                    canonical_url=f"https://space.bilibili.com/{quote(account_id, safe='')}",
                    title=_text(account_name, limit=2_000),
                    description=_text(node.get("usign") or node.get("desc"), limit=8_000),
                    author_id=account_id,
                    author_name=_text(account_name, limit=500),
                    captured_at=captured_at,
                    public_metrics=_metrics(node, {"followers": ("fans",)}),
                    thumbnail_url=_thumbnail(node.get("upic")),
                )
            )
            continue

        item_id = str(node.get("bvid") or "").strip()
        if not item_id:
            continue
        items.append(
            PlatformSearchItem(
                platform=SearchPlatform.BILIBILI,
                item_type=PlatformSearchItemType.POST,
                item_id=item_id,
                canonical_url=f"https://www.bilibili.com/video/{quote(item_id, safe='')}",
                title=_text(node.get("title"), limit=2_000),
                description=_text(node.get("description") or node.get("desc"), limit=8_000),
                author_id=str(node.get("mid") or "") or None,
                author_name=_text(node.get("author") or node.get("uname"), limit=500),
                author_public_metrics=_metrics(
                    node,
                    {"followers": ("fans",)},
                ),
                published_at=_timestamp(node.get("pubdate") or node.get("senddate")),
                captured_at=captured_at,
                public_metrics=_metrics(
                    node,
                    {
                        "plays": ("play", "view"),
                        "likes": ("like",),
                        "comments": ("video_review", "danmaku"),
                        "favorites": ("favorites", "favorite"),
                    },
                ),
                thumbnail_url=_thumbnail(node.get("pic")),
            )
        )
    return items


def _tiktok_items(
    *,
    payload: object,
    target: PlatformSearchTarget,
    captured_at: datetime,
) -> list[PlatformSearchItem]:
    items: list[PlatformSearchItem] = []
    for node in _walk_dicts(payload):
        if target is PlatformSearchTarget.ACCOUNTS:
            user = node.get("user") or node.get("user_info")
            if not isinstance(user, Mapping):
                continue
            account_id = str(user.get("uniqueId") or user.get("unique_id") or user.get("id") or "").strip()
            if not account_id:
                continue
            items.append(
                PlatformSearchItem(
                    platform=SearchPlatform.TIKTOK,
                    item_type=PlatformSearchItemType.ACCOUNT,
                    item_id=account_id,
                    canonical_url=f"https://www.tiktok.com/@{quote(account_id, safe='')}",
                    title=_text(user.get("nickname") or account_id, limit=2_000),
                    description=_text(user.get("signature"), limit=8_000),
                    author_id=str(user.get("id") or account_id),
                    author_name=_text(user.get("nickname") or account_id, limit=500),
                    captured_at=captured_at,
                    public_metrics=_metrics(
                        user.get("stats") or node.get("stats"),
                        {"followers": ("followerCount", "follower_count")},
                    ),
                    thumbnail_url=_thumbnail(user.get("avatarLarger") or user.get("avatar")),
                )
            )
            continue

        if "id" not in node or not isinstance(node.get("author"), Mapping):
            continue
        if not any(key in node for key in ("desc", "createTime", "stats", "video")):
            continue
        item_id = str(node.get("id") or "").strip()
        if not item_id:
            continue
        author = node["author"]
        username = str(author.get("uniqueId") or author.get("unique_id") or "").strip()
        canonical = f"https://www.tiktok.com/@{quote(username, safe='')}/video/{quote(item_id, safe='')}" if username else f"https://www.tiktok.com/video/{quote(item_id, safe='')}"
        video = node.get("video") if isinstance(node.get("video"), Mapping) else {}
        items.append(
            PlatformSearchItem(
                platform=SearchPlatform.TIKTOK,
                item_type=PlatformSearchItemType.POST,
                item_id=item_id,
                canonical_url=canonical,
                title=_text(node.get("desc"), limit=2_000),
                description=_text(node.get("desc"), limit=8_000),
                author_id=str(author.get("id") or username) or None,
                author_name=_text(author.get("nickname") or username, limit=500),
                author_public_metrics=_metrics(
                    author,
                    {"followers": ("followerCount", "follower_count")},
                ),
                published_at=_timestamp(node.get("createTime") or node.get("create_time")),
                captured_at=captured_at,
                public_metrics=_metrics(
                    node.get("stats"),
                    {
                        "plays": ("playCount", "play_count"),
                        "likes": ("diggCount", "digg_count"),
                        "comments": ("commentCount", "comment_count"),
                        "shares": ("shareCount", "share_count"),
                        "favorites": ("collectCount", "collect_count"),
                    },
                ),
                thumbnail_url=_thumbnail(video.get("cover") or video.get("originCover")),
            )
        )
    return items


_RESPONSE_PARSERS = {
    SearchPlatform.DOUYIN: _douyin_items,
    SearchPlatform.XIAOHONGSHU: _xiaohongshu_items,
    SearchPlatform.KUAISHOU: _kuaishou_items,
    SearchPlatform.BILIBILI: _bilibili_items,
    SearchPlatform.TIKTOK: _tiktok_items,
}


def _item_completeness(item: PlatformSearchItem) -> tuple[int, int]:
    populated = (
        sum(
            value is not None
            for value in (
                item.title,
                item.description,
                item.author_id,
                item.author_name,
                item.published_at,
                item.thumbnail_url,
            )
        )
        + len(item.public_metrics)
        + len(item.author_public_metrics)
    )
    return populated, len(item.title or "") + len(item.description or "")


def _deduplicate(items: Sequence[PlatformSearchItem], *, limit: int) -> tuple[PlatformSearchItem, ...]:
    by_id: dict[tuple[PlatformSearchItemType, str], PlatformSearchItem] = {}
    order: list[tuple[PlatformSearchItemType, str]] = []
    for item in items:
        key = (item.item_type, item.item_id)
        current = by_id.get(key)
        if current is None:
            by_id[key] = item
            order.append(key)
        elif _item_completeness(item) > _item_completeness(current):
            by_id[key] = item
    return tuple(by_id[key] for key in order[:limit])


def parse_platform_response(
    *,
    platform: SearchPlatform,
    target: PlatformSearchTarget,
    payload: object,
    captured_at: datetime,
    limit: int,
) -> tuple[PlatformSearchItem, ...]:
    parser = _RESPONSE_PARSERS.get(platform)
    if parser is None:
        return ()
    return _deduplicate(
        parser(payload=payload, target=target, captured_at=captured_at),
        limit=limit,
    )


_DOM_PATTERNS: dict[
    SearchPlatform,
    dict[PlatformSearchItemType, re.Pattern[str]],
] = {
    SearchPlatform.DOUYIN: {
        PlatformSearchItemType.POST: re.compile(r"/video/([0-9A-Za-z_-]+)"),
        PlatformSearchItemType.ACCOUNT: re.compile(r"/user/([^/?#]+)"),
    },
    SearchPlatform.XIAOHONGSHU: {
        PlatformSearchItemType.POST: re.compile(r"/(?:explore|discovery/item|note)/([0-9A-Za-z_-]+)"),
        PlatformSearchItemType.ACCOUNT: re.compile(r"/user/profile/([^/?#]+)"),
    },
    SearchPlatform.KUAISHOU: {
        PlatformSearchItemType.POST: re.compile(r"/short-video/([^/?#]+)"),
        PlatformSearchItemType.ACCOUNT: re.compile(r"/profile/([^/?#]+)"),
    },
    SearchPlatform.BILIBILI: {
        PlatformSearchItemType.POST: re.compile(r"/video/(BV[0-9A-Za-z]+)"),
        PlatformSearchItemType.ACCOUNT: re.compile(r"space\.bilibili\.com/([0-9]+)"),
    },
    SearchPlatform.TIKTOK: {
        PlatformSearchItemType.POST: re.compile(r"/@[^/?#]+/video/([0-9]+)"),
        PlatformSearchItemType.ACCOUNT: re.compile(r"/@([^/?#]+)"),
    },
}


def _parse_visible_links(
    *,
    platform: SearchPlatform,
    target: PlatformSearchTarget,
    links: Sequence[BrowserLinkObservation],
    captured_at: datetime,
    limit: int,
) -> tuple[PlatformSearchItem, ...]:
    item_type = PlatformSearchItemType.ACCOUNT if target is PlatformSearchTarget.ACCOUNTS else PlatformSearchItemType.POST
    pattern = _DOM_PATTERNS[platform][item_type]
    base = _BASE_URLS[platform]
    result: list[PlatformSearchItem] = []
    for link in links:
        url = _absolute_http_url(link.href, base=base)
        if url is None:
            continue
        host = urlsplit(url).hostname or ""
        if not _host_matches(host, _PLATFORM_HOSTS[platform]):
            continue
        match = pattern.search(url)
        if match is None:
            continue
        item_id = match.group(1)
        canonical = url.split("?", 1)[0].split("#", 1)[0]
        result.append(
            PlatformSearchItem(
                platform=platform,
                item_type=item_type,
                item_id=item_id,
                canonical_url=canonical,
                title=_text(link.text, limit=2_000),
                captured_at=captured_at,
            )
        )
    return _deduplicate(result, limit=limit)


def _response_url_is_relevant(platform: SearchPlatform, url: str) -> bool:
    lowered = url.lower()
    markers = {
        SearchPlatform.DOUYIN: ("search", "aweme"),
        SearchPlatform.XIAOHONGSHU: ("search", "note", "user"),
        SearchPlatform.KUAISHOU: ("graphql", "search"),
        SearchPlatform.BILIBILI: ("search", "web-interface"),
        SearchPlatform.TIKTOK: ("search", "item", "user"),
    }[platform]
    return any(marker in lowered for marker in markers)


def _detect_page_state(final_url: str, body_text: str) -> BrowserSearchPageState:
    lowered_url = final_url.lower()
    normalized = re.sub(r"\s+", " ", body_text).lower()
    restricted_markers = (
        "captcha",
        "verify you are human",
        "访问频繁",
        "安全验证",
        "完成验证",
        "操作频繁",
    )
    if any(marker in normalized for marker in restricted_markers):
        return BrowserSearchPageState.RESTRICTED
    login_markers = (
        "扫码登录",
        "手机号登录",
        "登录后查看",
        "log in to continue",
        "sign in to continue",
    )
    if "login" in lowered_url or any(marker in normalized for marker in login_markers):
        return BrowserSearchPageState.NEEDS_LOGIN
    return BrowserSearchPageState.READY


async def _read_relevant_response_json(
    *,
    platform: SearchPlatform,
    response: object,
) -> object | None:
    url = str(getattr(response, "url", ""))
    if not _response_url_is_relevant(platform, url):
        return None
    try:
        headers = await response.all_headers()
        content_type = str(headers.get("content-type", "")).lower()
        length = _number(headers.get("content-length"))
        if "json" not in content_type or (length is not None and length > 2_000_000):
            return None
        return await response.json()
    except Exception:
        return None


class LocalPlaywrightSearchRunner:
    """Run a visible local browser and keep raw browser data process-local."""

    def __init__(
        self,
        *,
        headless: bool = False,
        navigation_timeout_ms: int = 60_000,
        settle_ms: int = 1_500,
    ) -> None:
        self._headless = headless
        self._navigation_timeout_ms = navigation_timeout_ms
        self._settle_ms = settle_ms

    async def capture(
        self,
        *,
        url: str,
        platform: SearchPlatform,
        target: PlatformSearchTarget,
        page_size: int,
        storage_state: Mapping[str, object] | None,
    ) -> BrowserSearchCapture:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright browser support is not installed") from exc

        captured_at = datetime.now(UTC)
        payloads: list[object] = []
        pending: set[asyncio.Task[None]] = set()

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self._headless)
            try:
                context_options: dict[str, object] = {}
                if storage_state is not None:
                    context_options["storage_state"] = dict(storage_state)
                context = await browser.new_context(**context_options)
                page = await context.new_page()

                async def read_response(response) -> None:
                    if len(payloads) >= 24:
                        return
                    payload = await _read_relevant_response_json(
                        platform=platform,
                        response=response,
                    )
                    if payload is not None:
                        payloads.append(payload)

                def on_response(response) -> None:
                    task = asyncio.create_task(read_response(response))
                    pending.add(task)
                    task.add_done_callback(pending.discard)

                page.on("response", on_response)
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self._navigation_timeout_ms,
                )
                await page.wait_for_timeout(self._settle_ms)
                scrolls = min(12, max(2, (page_size + 9) // 10))
                for _ in range(scrolls):
                    await page.evaluate("window.scrollBy(0, Math.max(900, innerHeight))")
                    await page.wait_for_timeout(600)
                if pending:
                    await asyncio.gather(*tuple(pending), return_exceptions=True)

                raw_links = await page.locator("a[href]").evaluate_all(
                    """
                    els => els.slice(0, 1000).map(el => ({
                      href: el.href || el.getAttribute('href') || '',
                      text: (el.innerText || el.getAttribute('aria-label') || '').trim()
                    }))
                    """
                )
                visible_links = tuple(
                    BrowserLinkObservation(
                        href=str(item.get("href") or "")[:2_000],
                        text=str(item.get("text") or "")[:2_000],
                    )
                    for item in raw_links
                    if isinstance(item, Mapping) and item.get("href")
                )
                body_text = await page.locator("body").inner_text(timeout=5_000)
                final_url = page.url
                page_state = _detect_page_state(final_url, body_text[:20_000])
                page.remove_listener("response", on_response)
                if pending:
                    await asyncio.gather(*tuple(pending), return_exceptions=True)
                return BrowserSearchCapture(
                    captured_at=captured_at,
                    final_url=final_url,
                    page_state=page_state,
                    response_payloads=tuple(payloads),
                    visible_links=visible_links,
                )
            finally:
                await browser.close()


class PlaywrightPlatformSearchAdapter:
    capability_version = "local-playwright-search-v1"

    def __init__(
        self,
        *,
        platform: SearchPlatform,
        runner: BrowserSearchRunner | None = None,
    ) -> None:
        if platform not in _WEB_PLATFORMS:
            raise ValueError("platform requires a web search adapter")
        self.platform = platform
        self._runner = runner or LocalPlaywrightSearchRunner()

    def build_search_url(self, request: PlatformSearchRequest) -> str:
        if request.platform is not self.platform:
            raise ValueError("request platform does not match adapter")
        if request.target is PlatformSearchTarget.ACCOUNT_POSTS:
            url = _absolute_http_url(request.query)
            host = urlsplit(url or "").hostname or ""
            if url is None or not _host_matches(host, _PLATFORM_HOSTS[self.platform]):
                raise ValueError("account post search requires a platform account URL")
            parsed = urlsplit(url)
            clean_url = parsed._replace(query="", fragment="").geturl().rstrip("/")
            if self.platform is SearchPlatform.BILIBILI:
                return f"{clean_url}/video"
            return clean_url

        query = quote(request.query, safe="")
        query_plus = quote_plus(request.query, safe="")
        builders = {
            (SearchPlatform.DOUYIN, PlatformSearchTarget.CONTENT): (f"https://www.douyin.com/search/{query}?type=video"),
            (SearchPlatform.DOUYIN, PlatformSearchTarget.ACCOUNTS): (f"https://www.douyin.com/search/{query}?type=user"),
            (SearchPlatform.XIAOHONGSHU, PlatformSearchTarget.CONTENT): (f"https://www.xiaohongshu.com/search_result?keyword={query_plus}&source=web_search_result_notes"),
            (SearchPlatform.XIAOHONGSHU, PlatformSearchTarget.ACCOUNTS): (f"https://www.xiaohongshu.com/search_result?keyword={query_plus}&type=51"),
            (SearchPlatform.KUAISHOU, PlatformSearchTarget.CONTENT): (f"https://www.kuaishou.com/search/video?searchKey={query_plus}"),
            (SearchPlatform.KUAISHOU, PlatformSearchTarget.ACCOUNTS): (f"https://www.kuaishou.com/search/author?searchKey={query_plus}"),
            (SearchPlatform.BILIBILI, PlatformSearchTarget.CONTENT): (f"https://search.bilibili.com/all?keyword={query_plus}"),
            (SearchPlatform.BILIBILI, PlatformSearchTarget.ACCOUNTS): (f"https://search.bilibili.com/upuser?keyword={query_plus}"),
            (SearchPlatform.TIKTOK, PlatformSearchTarget.CONTENT): (f"https://www.tiktok.com/search/video?q={query_plus}"),
            (SearchPlatform.TIKTOK, PlatformSearchTarget.ACCOUNTS): (f"https://www.tiktok.com/search/user?q={query_plus}"),
        }
        return builders[(self.platform, request.target)]

    async def search(
        self,
        *,
        request: PlatformSearchRequest,
        credentials: LocalBrowserCredentials | None,
    ) -> PlatformSearchPage:
        storage_state = credentials.playwright_storage_state() if credentials is not None else None
        raw_capture = self._runner.capture(
            url=self.build_search_url(request),
            platform=self.platform,
            target=request.target,
            page_size=request.page_size,
            storage_state=storage_state,
        )
        capture = await raw_capture if inspect.isawaitable(raw_capture) else raw_capture
        if not isinstance(capture, BrowserSearchCapture):
            raise TypeError("browser runner returned an invalid capture")

        parsed: list[PlatformSearchItem] = []
        for payload in capture.response_payloads:
            parsed.extend(
                parse_platform_response(
                    platform=self.platform,
                    target=request.target,
                    payload=payload,
                    captured_at=capture.captured_at,
                    limit=request.page_size,
                )
            )
        parsed.extend(
            _parse_visible_links(
                platform=self.platform,
                target=request.target,
                links=capture.visible_links,
                captured_at=capture.captured_at,
                limit=request.page_size,
            )
        )
        items = _deduplicate(parsed, limit=request.page_size)
        source = PlatformSearchSource.AUTHENTICATED_BROWSER if credentials is not None else PlatformSearchSource.PUBLIC_BROWSER
        limitations = list(capture.limitations)
        if request.cursor is not None:
            limitations.append("This browser adapter does not yet expose a stable platform cursor.")

        if items:
            if capture.page_state is not BrowserSearchPageState.READY:
                limitations.append("The page changed state after some visible results were captured.")
            return PlatformSearchPage(
                platform=request.platform,
                target=request.target,
                query=request.query,
                requested_page_size=request.page_size,
                status=(PlatformSearchStatus.SUCCESS if capture.page_state is BrowserSearchPageState.READY else PlatformSearchStatus.PARTIAL),
                source=source,
                capability_version=self.capability_version,
                authenticated=credentials is not None,
                items=items,
                captured_at=capture.captured_at,
                limitations=tuple(limitations),
            )

        state_status = {
            BrowserSearchPageState.NEEDS_LOGIN: PlatformSearchStatus.NEEDS_LOGIN,
            BrowserSearchPageState.RESTRICTED: PlatformSearchStatus.RESTRICTED,
            BrowserSearchPageState.FAILED: PlatformSearchStatus.FAILED,
            BrowserSearchPageState.READY: PlatformSearchStatus.PARTIAL,
        }
        status = state_status[capture.page_state]
        error_details = {
            PlatformSearchStatus.NEEDS_LOGIN: (
                "login_required",
                "The local platform login is missing or expired.",
            ),
            PlatformSearchStatus.RESTRICTED: (
                "manual_verification_required",
                "The platform requested manual verification.",
            ),
            PlatformSearchStatus.FAILED: (
                "browser_capture_failed",
                "The local browser could not complete the search.",
            ),
            PlatformSearchStatus.PARTIAL: (
                None,
                None,
            ),
        }[status]
        if status is PlatformSearchStatus.PARTIAL:
            limitations.append("No structured or visible result was observed; empty results and page drift cannot yet be distinguished.")
        return PlatformSearchPage(
            platform=request.platform,
            target=request.target,
            query=request.query,
            requested_page_size=request.page_size,
            status=status,
            source=source,
            capability_version=self.capability_version,
            authenticated=credentials is not None,
            captured_at=capture.captured_at,
            limitations=tuple(limitations),
            error_code=error_details[0],
            error_message=error_details[1],
        )


DesktopSearchBridge = Callable[..., object | Awaitable[object]]


class DesktopSearchBridgeAdapter:
    """Bridge desktop-only platforms into the same strict search contract."""

    def __init__(
        self,
        *,
        platform: SearchPlatform,
        bridge: DesktopSearchBridge,
        capability_version: str,
    ) -> None:
        if platform is not SearchPlatform.WECHAT_CHANNELS:
            raise ValueError("desktop bridge currently supports WeChat Channels only")
        self.platform = platform
        self._bridge = bridge
        self.capability_version = capability_version

    async def search(
        self,
        *,
        request: PlatformSearchRequest,
        credentials: LocalBrowserCredentials | None,
    ) -> object:
        if request.platform is not self.platform:
            raise ValueError("request platform does not match adapter")
        raw = self._bridge(request=request, credentials=credentials)
        return await raw if inspect.isawaitable(raw) else raw


def build_platform_search_adapters(
    *,
    runner: BrowserSearchRunner | None = None,
    wechat_channels_bridge: DesktopSearchBridge | None = None,
    wechat_channels_capability_version: str | None = None,
) -> dict[SearchPlatform, object]:
    """Build the isolated adapter registry without implying live support."""
    adapters: dict[SearchPlatform, object] = {
        platform: PlaywrightPlatformSearchAdapter(platform=platform, runner=runner)
        for platform in (
            SearchPlatform.DOUYIN,
            SearchPlatform.XIAOHONGSHU,
            SearchPlatform.KUAISHOU,
            SearchPlatform.BILIBILI,
            SearchPlatform.TIKTOK,
        )
    }
    if wechat_channels_bridge is not None:
        capability_version = str(wechat_channels_capability_version or "").strip()
        if not capability_version:
            raise ValueError("wechat_channels_capability_version is required with a desktop bridge")
        adapters[SearchPlatform.WECHAT_CHANNELS] = DesktopSearchBridgeAdapter(
            platform=SearchPlatform.WECHAT_CHANNELS,
            bridge=wechat_channels_bridge,
            capability_version=capability_version,
        )
    return adapters


__all__ = [
    "BrowserLinkObservation",
    "BrowserSearchCapture",
    "BrowserSearchPageState",
    "BrowserSearchRunner",
    "DesktopSearchBridgeAdapter",
    "LocalPlaywrightSearchRunner",
    "PlaywrightPlatformSearchAdapter",
    "_read_relevant_response_json",
    "build_platform_search_adapters",
    "parse_platform_response",
]
