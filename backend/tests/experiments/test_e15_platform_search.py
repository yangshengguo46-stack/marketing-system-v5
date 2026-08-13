from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from experiments.e15_account_evidence.account_link_collection import (
    AccountLinkCollectionRequest,
    collect_account_link,
)
from experiments.e15_account_evidence.contracts import SourceRights
from experiments.e15_account_evidence.local_browser_credentials import (
    CdpLocalBrowserSessionCapture,
    LocalBrowserCredentialProvider,
    LocalBrowserSessionRegistry,
    register_local_browser_session,
)
from experiments.e15_account_evidence.platform_account_reader import (
    PlatformAccountReader,
    PlatformAccountReadError,
)
from experiments.e15_account_evidence.platform_search import (
    SUPPORTED_SEARCH_PLATFORMS,
    CrossPlatformSearchRequest,
    PlatformSearchItem,
    PlatformSearchItemType,
    PlatformSearchPage,
    PlatformSearchRequest,
    PlatformSearchSource,
    PlatformSearchStatus,
    PlatformSearchTarget,
    SearchPlatform,
    collect_platform_search,
    search_across_platforms,
)
from experiments.e15_account_evidence.platform_search_adapters import (
    BrowserLinkObservation,
    BrowserSearchCapture,
    BrowserSearchPageState,
    DesktopSearchBridgeAdapter,
    PlaywrightPlatformSearchAdapter,
    _read_relevant_response_json,
    build_platform_search_adapters,
    parse_platform_response,
)
from experiments.e15_account_evidence.source_snapshot import CollectionMethod

NOW = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
COOKIE_SECRET = "session-cookie-must-stay-local"


def _page(request: PlatformSearchRequest, *, item_id: str = "post-1") -> PlatformSearchPage:
    item_type = PlatformSearchItemType.ACCOUNT if request.target is PlatformSearchTarget.ACCOUNTS else PlatformSearchItemType.POST
    return PlatformSearchPage(
        platform=request.platform,
        target=request.target,
        query=request.query,
        requested_page_size=request.page_size,
        status=PlatformSearchStatus.SUCCESS,
        source=PlatformSearchSource.AUTHENTICATED_BROWSER,
        capability_version="fixture-v1",
        authenticated=request.session_ref is not None,
        items=(
            PlatformSearchItem(
                platform=request.platform,
                item_type=item_type,
                item_id=item_id,
                canonical_url=f"https://example.com/{request.platform.value}/{item_id}",
                title=f"{request.query} result",
                captured_at=NOW,
                public_metrics={"likes": 12},
            ),
        ),
        captured_at=NOW,
    )


class _Adapter:
    def __init__(self, *, fail_with: str | None = None) -> None:
        self.fail_with = fail_with
        self.received_storage_states: list[dict | None] = []

    async def search(self, *, request, credentials):
        self.received_storage_states.append(credentials.playwright_storage_state() if credentials is not None else None)
        if self.fail_with is not None:
            raise RuntimeError(self.fail_with)
        return _page(request)


def _write_storage_state(path: Path, *, cookie_domain: str = ".douyin.com") -> None:
    path.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "sessionid",
                        "value": COOKIE_SECRET,
                        "domain": cookie_domain,
                        "path": "/",
                    },
                    {
                        "name": "other-platform",
                        "value": "must-be-filtered",
                        "domain": ".example.com",
                        "path": "/",
                    },
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )


def test_supported_search_platforms_cover_the_six_product_platforms() -> None:
    assert SUPPORTED_SEARCH_PLATFORMS == (
        SearchPlatform.DOUYIN,
        SearchPlatform.XIAOHONGSHU,
        SearchPlatform.WECHAT_CHANNELS,
        SearchPlatform.KUAISHOU,
        SearchPlatform.BILIBILI,
        SearchPlatform.TIKTOK,
    )


@pytest.mark.asyncio
async def test_connector_can_read_local_cookie_without_exposing_it_in_result(
    tmp_path: Path,
) -> None:
    storage_state = tmp_path / "douyin-account-a.json"
    _write_storage_state(storage_state)
    provider = LocalBrowserCredentialProvider({(SearchPlatform.DOUYIN, "account-a"): storage_state})
    adapter = _Adapter()
    request = PlatformSearchRequest(
        platform=SearchPlatform.DOUYIN,
        target=PlatformSearchTarget.CONTENT,
        query="腕表",
        session_ref="account-a",
        page_size=30,
    )

    result = await collect_platform_search(
        request,
        adapter=adapter,
        credential_provider=provider,
    )

    assert adapter.received_storage_states[0]["cookies"] == [
        {
            "name": "sessionid",
            "value": COOKIE_SECRET,
            "domain": ".douyin.com",
            "path": "/",
        }
    ]
    serialized = result.model_dump_json()
    assert result.authenticated is True
    assert COOKIE_SECRET not in serialized
    assert "must-be-filtered" not in serialized
    assert COOKIE_SECRET not in repr(provider.load(SearchPlatform.DOUYIN, "account-a"))


@pytest.mark.asyncio
async def test_login_state_registration_is_account_scoped_and_persists_no_secret_index(
    tmp_path: Path,
) -> None:
    class SessionCapture:
        async def capture_storage_state(self, **kwargs):
            assert kwargs["platform"] is SearchPlatform.DOUYIN
            assert kwargs["session_ref"] == "user-a-account-a"
            return {
                "cookies": [
                    {
                        "name": "sessionid",
                        "value": COOKIE_SECRET,
                        "domain": ".douyin.com",
                        "path": "/",
                    },
                    {
                        "name": "foreign",
                        "value": "must-not-persist",
                        "domain": ".example.com",
                        "path": "/",
                    },
                ],
                "origins": [],
            }

    registry = LocalBrowserSessionRegistry(root=tmp_path)
    record = await register_local_browser_session(
        platform=SearchPlatform.DOUYIN,
        session_ref="user-a-account-a",
        registry=registry,
        capture=SessionCapture(),
    )

    assert record.platform == "douyin"
    assert record.session_ref == "user-a-account-a"
    assert record.cookie_count == 1
    assert record.state_path.is_file()
    assert record.state_path.stat().st_mode & 0o077 == 0
    assert COOKIE_SECRET not in registry.index_path.read_text(encoding="utf-8")
    provider = registry.credential_provider()
    state = provider.load(SearchPlatform.DOUYIN, "user-a-account-a")
    assert state.playwright_storage_state()["cookies"][0]["value"] == COOKIE_SECRET


@pytest.mark.asyncio
async def test_session_registration_rejects_invalid_account_reference(tmp_path: Path) -> None:
    class UnusedCapture:
        async def capture_storage_state(self, **kwargs):
            raise AssertionError("capture must not run")

    with pytest.raises(ValueError, match="session_ref"):
        await register_local_browser_session(
            platform=SearchPlatform.TIKTOK,
            session_ref="../another-user",
            registry=LocalBrowserSessionRegistry(root=tmp_path),
            capture=UnusedCapture(),
        )


@pytest.mark.asyncio
async def test_cdp_capture_reads_existing_local_browser_storage_without_closing_chrome() -> None:
    calls: list[str] = []

    class Context:
        async def storage_state(self):
            return {
                "cookies": [
                    {
                        "name": "sessionid",
                        "value": COOKIE_SECRET,
                        "domain": ".douyin.com",
                        "path": "/",
                    }
                ],
                "origins": [],
            }

    class Browser:
        contexts = [Context()]

        async def close(self):
            raise AssertionError("capturing storage state must not close local Chrome")

    async def connect(cdp_url: str):
        calls.append(cdp_url)
        return Browser()

    capture = CdpLocalBrowserSessionCapture(
        cdp_url="http://127.0.0.1:9222",
        connector=connect,
    )
    state = await capture.capture_storage_state(
        platform=SearchPlatform.DOUYIN,
        session_ref="user-a-account-a",
    )

    assert state["cookies"][0]["value"] == COOKIE_SECRET
    assert calls == ["http://127.0.0.1:9222"]


def test_cdp_capture_only_accepts_a_local_browser_endpoint() -> None:
    with pytest.raises(ValueError, match="local loopback"):
        CdpLocalBrowserSessionCapture(cdp_url="https://remote.example.com:9222")


@pytest.mark.asyncio
async def test_cookie_in_adapter_exception_is_redacted_from_result(tmp_path: Path) -> None:
    storage_state = tmp_path / "douyin-account-a.json"
    _write_storage_state(storage_state)
    provider = LocalBrowserCredentialProvider({(SearchPlatform.DOUYIN, "account-a"): storage_state})
    request = PlatformSearchRequest(
        platform=SearchPlatform.DOUYIN,
        target=PlatformSearchTarget.ACCOUNTS,
        query="腕表",
        session_ref="account-a",
    )

    result = await collect_platform_search(
        request,
        adapter=_Adapter(fail_with=f"request failed with Cookie: {COOKIE_SECRET}"),
        credential_provider=provider,
    )

    assert result.status is PlatformSearchStatus.FAILED
    assert result.error_code == "collector_failed"
    assert COOKIE_SECRET not in result.model_dump_json()


@pytest.mark.asyncio
async def test_adapter_raw_cookie_or_page_payload_is_rejected_as_schema_drift() -> None:
    class LeakyAdapter:
        async def search(self, *, request, credentials):
            payload = _page(request).model_dump(mode="json")
            payload["cookies"] = {"sessionid": COOKIE_SECRET}
            payload["raw_html"] = "<html>full page</html>"
            return payload

    result = await collect_platform_search(
        PlatformSearchRequest(
            platform=SearchPlatform.TIKTOK,
            target=PlatformSearchTarget.CONTENT,
            query="watch",
        ),
        adapter=LeakyAdapter(),
    )

    assert result.status is PlatformSearchStatus.SCHEMA_DRIFT
    assert result.items == ()
    assert COOKIE_SECRET not in result.model_dump_json()


@pytest.mark.asyncio
async def test_all_platform_search_calls_every_platform_and_isolates_one_failure() -> None:
    adapters = {platform: _Adapter() for platform in SUPPORTED_SEARCH_PLATFORMS}
    adapters[SearchPlatform.WECHAT_CHANNELS] = _Adapter(fail_with="desktop search unavailable")

    result = await search_across_platforms(
        CrossPlatformSearchRequest(
            query="腕表",
            target=PlatformSearchTarget.CONTENT,
            page_size_per_platform=40,
        ),
        adapters=adapters,
    )

    assert tuple(page.platform for page in result.pages) == SUPPORTED_SEARCH_PLATFORMS
    assert len(result.pages) == 6
    assert result.page_for(SearchPlatform.WECHAT_CHANNELS).status is PlatformSearchStatus.FAILED
    assert all(result.page_for(platform).status is PlatformSearchStatus.SUCCESS for platform in SUPPORTED_SEARCH_PLATFORMS if platform is not SearchPlatform.WECHAT_CHANNELS)


@pytest.mark.asyncio
async def test_all_platform_search_reports_missing_adapter_without_cancelling_others() -> None:
    result = await search_across_platforms(
        CrossPlatformSearchRequest(
            query="黄金礼品",
            target=PlatformSearchTarget.ACCOUNTS,
        ),
        adapters={SearchPlatform.DOUYIN: _Adapter()},
    )

    assert result.page_for(SearchPlatform.DOUYIN).status is PlatformSearchStatus.SUCCESS
    assert result.page_for(SearchPlatform.TIKTOK).status is PlatformSearchStatus.UNAVAILABLE


def test_search_contract_supports_cursor_pagination_without_a_tiny_total_cap() -> None:
    request = PlatformSearchRequest(
        platform=SearchPlatform.BILIBILI,
        target=PlatformSearchTarget.ACCOUNT_POSTS,
        query="account://watch-expert",
        page_size=100,
        cursor="next-page-token",
    )

    assert request.page_size == 100
    assert request.cursor == "next-page-token"


def test_search_page_rejects_cross_platform_items() -> None:
    request = PlatformSearchRequest(
        platform=SearchPlatform.DOUYIN,
        target=PlatformSearchTarget.CONTENT,
        query="腕表",
    )
    payload = _page(request).model_dump()
    payload["items"][0]["platform"] = SearchPlatform.TIKTOK

    with pytest.raises(ValueError, match="crosses platform boundary"):
        PlatformSearchPage.model_validate(payload)


@pytest.mark.parametrize(
    ("platform", "target", "payload", "expected_id", "expected_url"),
    [
        (
            SearchPlatform.DOUYIN,
            PlatformSearchTarget.CONTENT,
            {
                "data": [
                    {
                        "aweme_info": {
                            "aweme_id": "71001",
                            "desc": "腕表与人的故事",
                            "create_time": 1_700_000_000,
                            "author": {"sec_uid": "dy-user", "nickname": "腕表作者"},
                            "statistics": {"digg_count": 30, "comment_count": 4},
                        }
                    }
                ]
            },
            "71001",
            "https://www.douyin.com/video/71001",
        ),
        (
            SearchPlatform.XIAOHONGSHU,
            PlatformSearchTarget.CONTENT,
            {
                "items": [
                    {
                        "note_card": {
                            "note_id": "64abc",
                            "display_title": "通勤腕表怎么选",
                            "user": {"user_id": "xhs-user", "nickname": "小表姐"},
                            "interact_info": {"liked_count": "18", "comment_count": "2"},
                        }
                    }
                ]
            },
            "64abc",
            "https://www.xiaohongshu.com/explore/64abc",
        ),
        (
            SearchPlatform.KUAISHOU,
            PlatformSearchTarget.CONTENT,
            {
                "data": {
                    "visionSearchPhoto": {
                        "feeds": [
                            {
                                "photo": {
                                    "id": "ks01",
                                    "caption": "修表的一天",
                                    "realLikeCount": 8,
                                    "commentCount": 1,
                                },
                                "author": {"id": "ks-user", "name": "修表师"},
                            }
                        ]
                    }
                }
            },
            "ks01",
            "https://www.kuaishou.com/short-video/ks01",
        ),
        (
            SearchPlatform.BILIBILI,
            PlatformSearchTarget.CONTENT,
            {
                "data": {
                    "result": [
                        {
                            "bvid": "BV1watch",
                            "title": '<em class="keyword">腕表</em>历史',
                            "author": "钟表研究所",
                            "mid": 42,
                            "play": 120,
                            "like": 12,
                            "pubdate": 1_700_000_000,
                        }
                    ]
                }
            },
            "BV1watch",
            "https://www.bilibili.com/video/BV1watch",
        ),
        (
            SearchPlatform.TIKTOK,
            PlatformSearchTarget.CONTENT,
            {
                "item_list": [
                    {
                        "id": "tt01",
                        "desc": "watch restoration",
                        "createTime": 1_700_000_000,
                        "author": {"uniqueId": "watchmaker", "nickname": "Watchmaker"},
                        "stats": {"diggCount": 77, "commentCount": 6},
                    }
                ]
            },
            "tt01",
            "https://www.tiktok.com/@watchmaker/video/tt01",
        ),
    ],
)
def test_platform_response_parsers_normalize_public_content(
    platform: SearchPlatform,
    target: PlatformSearchTarget,
    payload: dict,
    expected_id: str,
    expected_url: str,
) -> None:
    rows = parse_platform_response(
        platform=platform,
        target=target,
        payload=payload,
        captured_at=NOW,
        limit=20,
    )

    assert rows[0].item_id == expected_id
    assert rows[0].canonical_url == expected_url
    assert rows[0].platform is platform
    assert rows[0].item_type is PlatformSearchItemType.POST


def test_account_search_parser_keeps_account_and_post_semantics_separate() -> None:
    rows = parse_platform_response(
        platform=SearchPlatform.DOUYIN,
        target=PlatformSearchTarget.ACCOUNTS,
        payload={
            "data": [
                {
                    "user_list": [
                        {
                            "user_info": {
                                "uid": "dy-account-1",
                                "sec_uid": "MS4wLjABAAAA-account-1",
                                "nickname": "送礼研究所",
                                "signature": "只研究怎么把礼送对",
                                "follower_count": 321,
                            }
                        }
                    ]
                }
            ]
        },
        captured_at=NOW,
        limit=20,
    )

    assert rows[0].item_type is PlatformSearchItemType.ACCOUNT
    assert rows[0].item_id == "MS4wLjABAAAA-account-1"
    assert rows[0].canonical_url == ("https://www.douyin.com/user/MS4wLjABAAAA-account-1")
    assert rows[0].public_metrics == {"followers": 321}


def test_duplicate_post_parser_prefers_author_metrics_in_the_richer_observation() -> None:
    rows = parse_platform_response(
        platform=SearchPlatform.DOUYIN,
        target=PlatformSearchTarget.ACCOUNT_POSTS,
        payload={
            "data": [
                {
                    "aweme_info": {
                        "aweme_id": "same-post",
                        "desc": "同一条作品",
                        "author": {
                            "sec_uid": "same-account",
                            "nickname": "目标账号",
                        },
                    }
                },
                {
                    "aweme_info": {
                        "aweme_id": "same-post",
                        "desc": "同一条作品",
                        "author": {
                            "sec_uid": "same-account",
                            "nickname": "目标账号",
                            "follower_count": 321,
                        },
                    }
                },
            ]
        },
        captured_at=NOW,
        limit=20,
    )

    assert len(rows) == 1
    assert rows[0].author_public_metrics == {"followers": 321}


@pytest.mark.parametrize(
    ("platform", "target", "expected_fragment"),
    [
        (SearchPlatform.DOUYIN, PlatformSearchTarget.CONTENT, "douyin.com/search/"),
        (SearchPlatform.DOUYIN, PlatformSearchTarget.ACCOUNTS, "type=user"),
        (SearchPlatform.XIAOHONGSHU, PlatformSearchTarget.CONTENT, "xiaohongshu.com/search_result"),
        (SearchPlatform.KUAISHOU, PlatformSearchTarget.CONTENT, "kuaishou.com/search/video"),
        (SearchPlatform.BILIBILI, PlatformSearchTarget.CONTENT, "search.bilibili.com/all"),
        (SearchPlatform.TIKTOK, PlatformSearchTarget.CONTENT, "tiktok.com/search/video"),
    ],
)
def test_web_adapter_builds_platform_specific_search_urls(
    platform: SearchPlatform,
    target: PlatformSearchTarget,
    expected_fragment: str,
) -> None:
    adapter = PlaywrightPlatformSearchAdapter(platform=platform)

    url = adapter.build_search_url(
        PlatformSearchRequest(
            platform=platform,
            target=target,
            query="腕表 repair",
        )
    )

    assert expected_fragment in url
    assert "腕表 repair" not in url


def test_web_adapter_requires_an_account_url_for_account_post_search() -> None:
    adapter = PlaywrightPlatformSearchAdapter(platform=SearchPlatform.TIKTOK)

    with pytest.raises(ValueError, match="account URL"):
        adapter.build_search_url(
            PlatformSearchRequest(
                platform=SearchPlatform.TIKTOK,
                target=PlatformSearchTarget.ACCOUNT_POSTS,
                query="watchmaker",
            )
        )


@pytest.mark.parametrize(
    ("platform", "account_url", "expected_url"),
    [
        (
            SearchPlatform.BILIBILI,
            "https://space.bilibili.com/451739017",
            "https://space.bilibili.com/451739017/video",
        ),
        (
            SearchPlatform.DOUYIN,
            "https://www.douyin.com/user/account-id?from=search",
            "https://www.douyin.com/user/account-id",
        ),
        (
            SearchPlatform.TIKTOK,
            "https://www.tiktok.com/@watchmaker?lang=en",
            "https://www.tiktok.com/@watchmaker",
        ),
    ],
)
def test_account_post_search_uses_the_platform_work_list_url(
    platform: SearchPlatform,
    account_url: str,
    expected_url: str,
) -> None:
    adapter = PlaywrightPlatformSearchAdapter(platform=platform)

    url = adapter.build_search_url(
        PlatformSearchRequest(
            platform=platform,
            target=PlatformSearchTarget.ACCOUNT_POSTS,
            query=account_url,
        )
    )

    assert url == expected_url


@pytest.mark.asyncio
async def test_playwright_adapter_uses_cookie_locally_and_returns_only_normalized_rows(
    tmp_path: Path,
) -> None:
    class Runner:
        def __init__(self) -> None:
            self.storage_state = None

        async def capture(self, **kwargs):
            self.storage_state = kwargs["storage_state"]
            return BrowserSearchCapture(
                captured_at=NOW,
                final_url=kwargs["url"],
                page_state=BrowserSearchPageState.READY,
                response_payloads=(
                    {
                        "data": [
                            {
                                "aweme_info": {
                                    "aweme_id": "71002",
                                    "desc": "送礼为什么最怕自我感动",
                                    "author": {
                                        "sec_uid": "gift-author",
                                        "nickname": "送礼研究所",
                                    },
                                    "statistics": {"digg_count": 99},
                                }
                            }
                        ]
                    },
                ),
                visible_links=(
                    BrowserLinkObservation(
                        href="https://www.douyin.com/video/71002",
                        text="送礼为什么最怕自我感动",
                    ),
                ),
            )

    storage_state = tmp_path / "douyin-account-a.json"
    _write_storage_state(storage_state)
    provider = LocalBrowserCredentialProvider({(SearchPlatform.DOUYIN, "account-a"): storage_state})
    runner = Runner()
    request = PlatformSearchRequest(
        platform=SearchPlatform.DOUYIN,
        target=PlatformSearchTarget.CONTENT,
        query="送礼",
        session_ref="account-a",
    )

    result = await collect_platform_search(
        request,
        adapter=PlaywrightPlatformSearchAdapter(
            platform=SearchPlatform.DOUYIN,
            runner=runner,
        ),
        credential_provider=provider,
    )

    assert runner.storage_state["cookies"][0]["value"] == COOKIE_SECRET
    assert result.items[0].item_id == "71002"
    assert len(result.items) == 1
    assert COOKIE_SECRET not in result.model_dump_json()


@pytest.mark.asyncio
async def test_closed_page_response_is_ignored_without_leaking_runner_error() -> None:
    class ClosedResponse:
        url = "https://www.douyin.com/aweme/v1/web/general/search/"

        async def all_headers(self):
            raise RuntimeError("Target page, context or browser has been closed")

    assert (
        await _read_relevant_response_json(
            platform=SearchPlatform.DOUYIN,
            response=ClosedResponse(),
        )
        is None
    )


@pytest.mark.asyncio
async def test_duplicate_dom_links_merge_into_the_richer_public_observation() -> None:
    class Runner:
        async def capture(self, **kwargs):
            return BrowserSearchCapture(
                captured_at=NOW,
                final_url=kwargs["url"],
                page_state=BrowserSearchPageState.READY,
                visible_links=(
                    BrowserLinkObservation(
                        href="https://www.bilibili.com/video/BV1watch/",
                        text="2.9万 210 19:07",
                    ),
                    BrowserLinkObservation(
                        href="https://www.bilibili.com/video/BV1watch/",
                        text="机械表到底是买机芯还是买工具？",
                    ),
                ),
            )

    request = PlatformSearchRequest(
        platform=SearchPlatform.BILIBILI,
        target=PlatformSearchTarget.CONTENT,
        query="腕表",
        page_size=5,
    )
    result = await collect_platform_search(
        request,
        adapter=PlaywrightPlatformSearchAdapter(
            platform=SearchPlatform.BILIBILI,
            runner=Runner(),
        ),
    )

    assert len(result.items) == 1
    assert result.items[0].title == "机械表到底是买机芯还是买工具？"


@pytest.mark.asyncio
async def test_desktop_bridge_uses_same_strict_result_contract() -> None:
    calls: list[dict] = []

    async def bridge(**kwargs):
        calls.append(kwargs)
        request = kwargs["request"]
        return _page(request, item_id="channels-post-1")

    adapter = DesktopSearchBridgeAdapter(
        platform=SearchPlatform.WECHAT_CHANNELS,
        bridge=bridge,
        capability_version="desktop-fixture-v1",
    )
    request = PlatformSearchRequest(
        platform=SearchPlatform.WECHAT_CHANNELS,
        target=PlatformSearchTarget.CONTENT,
        query="腕表",
    )

    result = await collect_platform_search(request, adapter=adapter)

    assert calls == [{"request": request, "credentials": None}]
    assert result.items[0].item_id == "channels-post-1"


def test_default_adapter_registry_keeps_desktop_execution_optional() -> None:
    adapters = build_platform_search_adapters()

    assert set(adapters) == {
        SearchPlatform.DOUYIN,
        SearchPlatform.XIAOHONGSHU,
        SearchPlatform.KUAISHOU,
        SearchPlatform.BILIBILI,
        SearchPlatform.TIKTOK,
    }
    assert SearchPlatform.WECHAT_CHANNELS not in adapters

    async def bridge(**_kwargs):
        raise AssertionError("bridge should not run while building the registry")

    with_desktop = build_platform_search_adapters(
        wechat_channels_bridge=bridge,
        wechat_channels_capability_version="ui-tars-desktop-candidate-v1",
    )

    assert set(with_desktop) == set(SUPPORTED_SEARCH_PLATFORMS)
    assert isinstance(
        with_desktop[SearchPlatform.WECHAT_CHANNELS],
        DesktopSearchBridgeAdapter,
    )


@pytest.mark.asyncio
async def test_platform_account_reader_turns_account_posts_into_snapshot_input(
    tmp_path: Path,
) -> None:
    class Runner:
        async def capture(self, **kwargs):
            assert kwargs["url"] == "https://v.douyin.com/short-account-link"
            assert kwargs["storage_state"]["cookies"][0]["value"] == COOKIE_SECRET
            return BrowserSearchCapture(
                captured_at=NOW,
                final_url="https://www.douyin.com/user/account-sec-uid",
                page_state=BrowserSearchPageState.READY,
                response_payloads=(
                    {
                        "data": [
                            {
                                "aweme_info": {
                                    "aweme_id": "71001",
                                    "desc": "腕表与人的故事",
                                    "author": {
                                        "sec_uid": "account-sec-uid",
                                        "nickname": "腕表研究所",
                                        "follower_count": 2_400,
                                        "total_favorited": 16_000,
                                    },
                                    "statistics": {"digg_count": 30},
                                }
                            },
                            {
                                "aweme_info": {
                                    "aweme_id": "71002",
                                    "desc": "一块表如何成为纪念物",
                                    "author": {
                                        "sec_uid": "account-sec-uid",
                                        "nickname": "腕表研究所",
                                        "follower_count": 2_400,
                                        "total_favorited": 16_000,
                                    },
                                    "statistics": {"digg_count": 20},
                                }
                            },
                        ]
                    },
                ),
            )

    storage_state = tmp_path / "douyin-account-a.json"
    _write_storage_state(storage_state)
    provider = LocalBrowserCredentialProvider({(SearchPlatform.DOUYIN, "account-a"): storage_state})
    reader = PlatformAccountReader(
        platform=SearchPlatform.DOUYIN,
        adapter=PlaywrightPlatformSearchAdapter(
            platform=SearchPlatform.DOUYIN,
            runner=Runner(),
        ),
        credential_provider=provider,
        session_ref="account-a",
    )

    observation = await reader(
        requested_url="https://v.douyin.com/short-account-link?share=1",
        max_posts=12,
    )

    assert observation.profile.account_id == "account-sec-uid"
    assert observation.profile.display_name == "腕表研究所"
    assert observation.profile.canonical_url == ("https://www.douyin.com/user/account-sec-uid")
    assert [post.post_id for post in observation.posts] == ["71001", "71002"]
    assert observation.posts[0].public_metrics == {"likes": 30}
    assert observation.profile.public_metrics == {
        "followers": 2_400,
        "likes_received": 16_000,
    }
    assert COOKIE_SECRET not in observation.model_dump_json()


@pytest.mark.asyncio
async def test_platform_account_reader_drops_conflicting_author_metrics() -> None:
    class ConflictingAdapter:
        async def search(self, *, request, credentials):
            del credentials
            page = _page(request, item_id="post-a").model_dump()
            page["items"] = list(page["items"])
            page["items"][0].update(
                {
                    "author_id": "account-a",
                    "author_name": "目标账号",
                    "author_public_metrics": {"followers": 100},
                }
            )
            page["items"].append(
                PlatformSearchItem(
                    platform=request.platform,
                    item_type=PlatformSearchItemType.POST,
                    item_id="post-b",
                    canonical_url="https://www.douyin.com/video/post-b",
                    author_id="account-a",
                    author_name="目标账号",
                    author_public_metrics={"followers": 101},
                    captured_at=NOW,
                ).model_dump()
            )
            return page

    observation = await PlatformAccountReader(
        platform=SearchPlatform.DOUYIN,
        adapter=ConflictingAdapter(),
    )(
        requested_url="https://www.douyin.com/user/account-a",
        max_posts=12,
    )

    assert observation.profile.public_metrics == {}
    assert any("followers" in limitation for limitation in observation.limitations)


@pytest.mark.asyncio
async def test_platform_account_reader_rejects_mixed_account_posts() -> None:
    class MixedAdapter:
        async def search(self, *, request, credentials):
            del credentials
            page = _page(request, item_id="post-a").model_dump()
            page["items"] = list(page["items"])
            page["items"].append(
                PlatformSearchItem(
                    platform=request.platform,
                    item_type=PlatformSearchItemType.POST,
                    item_id="post-b",
                    canonical_url="https://www.douyin.com/video/post-b",
                    author_id="account-b",
                    author_name="另一个账号",
                    captured_at=NOW,
                ).model_dump()
            )
            page["items"][0]["author_id"] = "account-a"
            page["items"][0]["author_name"] = "目标账号"
            return page

    reader = PlatformAccountReader(
        platform=SearchPlatform.DOUYIN,
        adapter=MixedAdapter(),
    )

    with pytest.raises(PlatformAccountReadError, match="multiple accounts"):
        await reader(
            requested_url="https://www.douyin.com/user/account-a",
            max_posts=12,
        )


@pytest.mark.asyncio
async def test_platform_account_reader_preserves_unknown_display_name() -> None:
    class IdOnlyAdapter:
        async def search(self, *, request, credentials):
            del credentials
            page = _page(request).model_dump()
            page["items"][0]["author_id"] = "account-a"
            page["items"][0]["author_name"] = None
            return page

    observation = await PlatformAccountReader(
        platform=SearchPlatform.DOUYIN,
        adapter=IdOnlyAdapter(),
    )(
        requested_url="https://www.douyin.com/user/account-a",
        max_posts=12,
    )

    assert observation.profile.account_id == "account-a"
    assert observation.profile.display_name is None


@pytest.mark.asyncio
async def test_platform_account_reader_rejects_post_without_author_identity() -> None:
    class MissingAuthorAdapter:
        async def search(self, *, request, credentials):
            del credentials
            page = _page(request).model_dump()
            page["items"][0]["author_id"] = None
            return page

    reader = PlatformAccountReader(
        platform=SearchPlatform.DOUYIN,
        adapter=MissingAuthorAdapter(),
    )

    with pytest.raises(PlatformAccountReadError, match="no stable account identity"):
        await reader(
            requested_url="https://www.douyin.com/user/account-a",
            max_posts=12,
        )


@pytest.mark.asyncio
async def test_platform_account_reader_connects_to_content_addressed_snapshot(
    tmp_path: Path,
) -> None:
    class Adapter:
        async def search(self, *, request, credentials):
            del credentials
            page = _page(request).model_dump()
            page["items"][0]["author_id"] = "account-a"
            page["items"][0]["author_name"] = "目标账号"
            return page

    request = AccountLinkCollectionRequest(
        requested_url="https://www.douyin.com/user/account-a",
        collection_method=CollectionMethod.VISIBLE_BROWSER_AUTHORIZED,
        source_rights=SourceRights.ANALYSIS_ONLY,
        rights_ref="request://local-account-read/test",
        max_posts=12,
        cache_root=tmp_path,
    )
    result = await collect_account_link(
        request,
        collector=PlatformAccountReader(
            platform=SearchPlatform.DOUYIN,
            adapter=Adapter(),
        ),
    )

    assert result.snapshot.profile.account_id == "account-a"
    assert result.snapshot.posts[0].post_id == "post-1"
    assert result.cache.path.is_file()
    assert result.cache.snapshot_sha256 in str(result.cache.path)


@pytest.mark.asyncio
async def test_tiktok_reader_keeps_requested_public_handle_url() -> None:
    class Adapter:
        async def search(self, *, request, credentials):
            del credentials
            page = _page(request).model_dump()
            page["items"][0]["author_id"] = "numeric-user-id"
            page["items"][0]["author_name"] = "Watchmaker"
            return page

    observation = await PlatformAccountReader(
        platform=SearchPlatform.TIKTOK,
        adapter=Adapter(),
    )(
        requested_url="https://www.tiktok.com/@watchmaker?lang=en",
        max_posts=12,
    )

    assert observation.profile.account_id == "numeric-user-id"
    assert observation.profile.canonical_url == "https://www.tiktok.com/@watchmaker"


@pytest.mark.asyncio
async def test_platform_account_reader_keeps_explicit_platform_failure() -> None:
    class LoginRequiredAdapter:
        async def search(self, *, request, credentials):
            del credentials
            return PlatformSearchPage(
                platform=request.platform,
                target=request.target,
                query=request.query,
                requested_page_size=request.page_size,
                status=PlatformSearchStatus.NEEDS_LOGIN,
                source=PlatformSearchSource.PUBLIC_BROWSER,
                capability_version="fixture-v1",
                authenticated=False,
                captured_at=NOW,
                error_code="login_required",
                error_message="Login is required.",
            )

    reader = PlatformAccountReader(
        platform=SearchPlatform.XIAOHONGSHU,
        adapter=LoginRequiredAdapter(),
    )

    with pytest.raises(PlatformAccountReadError, match="needs_login"):
        await reader(
            requested_url="https://www.xiaohongshu.com/user/profile/account-a",
            max_posts=12,
        )
