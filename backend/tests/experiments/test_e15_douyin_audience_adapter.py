from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from experiments.e15_account_evidence.audience_collection import (
    AudienceCollectionRequest,
    AudienceCollectionSource,
    AudienceCollectionStatus,
    AudienceDataset,
    AudienceDatasetStatus,
    collect_audience_intelligence,
)
from experiments.e15_account_evidence.contracts import SourceRights, canonical_sha256
from experiments.e15_account_evidence.douyin_audience_adapter import (
    DouyinAuthenticatedAudienceAdapter,
    DouyinCommentCapture,
    DouyinCommentPayloadError,
    RawDouyinComment,
    _trigger_comment_loading,
    parse_douyin_comment_payload,
)
from experiments.e15_account_evidence.local_browser_credentials import (
    LocalBrowserCredentialProvider,
)
from experiments.e15_account_evidence.platform_search import SearchPlatform
from experiments.e15_account_evidence.source_snapshot import (
    AccountProfileObservation,
    AccountSourceSnapshot,
    CollectionMethod,
    PostListObservation,
)

NOW = datetime(2026, 8, 13, 15, 0, tzinfo=UTC)
RAW_ACTOR_ID = "raw-platform-actor-must-not-persist"
COOKIE_VALUE = "browser-cookie-must-not-persist"


def _source() -> AccountSourceSnapshot:
    return AccountSourceSnapshot(
        profile=AccountProfileObservation(
            platform="douyin",
            account_id="daneng-account",
            canonical_url="https://www.douyin.com/user/daneng-account",
            display_name="大能",
            visible_work_count=572,
            public_metrics={"followers": 9_400_000},
            captured_at=NOW,
        ),
        posts=(
            PostListObservation(
                post_id="watch-post",
                canonical_url="https://www.douyin.com/video/watch-post",
                caption="你都用过啥签名？",
                captured_at=NOW,
                public_metrics={"comments": 1_156, "likes": 11_368},
            ),
            PostListObservation(
                post_id="declutter-post",
                canonical_url="https://www.douyin.com/video/declutter-post",
                caption="帮我想想这些怎么才能到有需要的人手上",
                captured_at=NOW,
                public_metrics={"comments": 11_771, "likes": 13_269},
            ),
        ),
        collection_method=CollectionMethod.VISIBLE_BROWSER_AUTHORIZED,
        source_rights=SourceRights.ANALYSIS_ONLY,
        rights_ref="rights://public-comparison/daneng",
        requested_url="https://v.douyin.com/example/",
        sample_basis="Bounded account sample.",
        captured_at=NOW,
    )


def _provider(tmp_path: Path) -> LocalBrowserCredentialProvider:
    state = tmp_path / "douyin.json"
    state.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "sessionid",
                        "value": COOKIE_VALUE,
                        "domain": ".douyin.com",
                        "path": "/",
                    }
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )
    return LocalBrowserCredentialProvider({(SearchPlatform.DOUYIN, "local-daneng"): state})


class _Runner:
    def __init__(self, capture: DouyinCommentCapture) -> None:
        self.capture_result = capture
        self.post_urls: tuple[str, ...] = ()
        self.max_interactions: int | None = None

    async def capture(self, *, post_urls, storage_state, max_interactions):
        assert storage_state["cookies"][0]["value"] == COOKIE_VALUE
        assert max_interactions > 0
        self.post_urls = tuple(post_urls)
        self.max_interactions = max_interactions
        return self.capture_result


class _MustNotRun:
    async def capture(self, **_kwargs):
        raise AssertionError("the interaction runner must not be called")


@pytest.mark.asyncio
async def test_authenticated_douyin_audience_sample_is_bounded_and_pseudonymized(
    tmp_path: Path,
) -> None:
    source = _source()
    source_sha256 = canonical_sha256(source.model_dump(mode="json"))
    runner = _Runner(
        DouyinCommentCapture(
            captured_at=NOW + timedelta(hours=1),
            attempted_post_ids=("watch-post",),
            comments=(
                RawDouyinComment(
                    comment_id="comment-1",
                    post_id="watch-post",
                    raw_actor_id=RAW_ACTOR_ID,
                    text="微信签名：没有眉毛",
                    occurred_at=NOW + timedelta(minutes=10),
                    visible_like_count=137,
                    visible_reply_count=7,
                ),
            ),
        )
    )
    adapter = DouyinAuthenticatedAudienceAdapter(
        source=source,
        runner=runner,
        local_actor_salt="local-only-pseudonym-salt",
        post_ids=("watch-post",),
    )

    result = await collect_audience_intelligence(
        AudienceCollectionRequest(
            platform=SearchPlatform.DOUYIN,
            account_id="daneng-account",
            account_url=source.profile.canonical_url,
            source_account_snapshot_sha256=source_sha256,
            datasets=(
                AudienceDataset.ACCOUNT_SCALE,
                AudienceDataset.CONTENT_INTERACTIONS,
                AudienceDataset.FOLLOWER_DEMOGRAPHICS,
            ),
            session_ref="local-daneng",
            max_interactions=20,
        ),
        adapter=adapter,
        credential_provider=_provider(tmp_path),
    )

    coverage = {item.dataset: item for item in result.coverage}
    assert result.status is AudienceCollectionStatus.PARTIAL
    assert result.source is AudienceCollectionSource.AUTHENTICATED_PLATFORM
    assert result.authenticated is True
    assert coverage[AudienceDataset.ACCOUNT_SCALE].status is AudienceDatasetStatus.COLLECTED
    assert coverage[AudienceDataset.CONTENT_INTERACTIONS].status is AudienceDatasetStatus.PARTIAL
    assert coverage[AudienceDataset.FOLLOWER_DEMOGRAPHICS].status is AudienceDatasetStatus.UNAVAILABLE
    assert runner.post_urls == ("https://www.douyin.com/video/watch-post",)
    assert runner.max_interactions == 20
    assert result.interactions[0].item_text == "你都用过啥签名？"
    assert result.interactions[0].public_metrics == {"likes": 137, "replies": 7}
    assert result.interactions[0].actor_ref.startswith("actor://sha256/")
    serialized = result.model_dump_json()
    assert RAW_ACTOR_ID not in serialized
    assert COOKIE_VALUE not in serialized
    assert "评论样本" not in serialized
    assert any(metric.metric_name == "followers.total" for metric in result.metrics)


@pytest.mark.asyncio
async def test_adapter_rejects_a_comment_for_a_post_outside_the_source_snapshot(
    tmp_path: Path,
) -> None:
    source = _source()
    runner = _Runner(
        DouyinCommentCapture(
            captured_at=NOW + timedelta(hours=1),
            attempted_post_ids=("watch-post",),
            comments=(
                RawDouyinComment(
                    comment_id="foreign-comment",
                    post_id="another-account-post",
                    raw_actor_id=RAW_ACTOR_ID,
                    text="不属于当前账号",
                    occurred_at=NOW,
                ),
            ),
        )
    )
    adapter = DouyinAuthenticatedAudienceAdapter(
        source=source,
        runner=runner,
        local_actor_salt="local-only-pseudonym-salt",
        post_ids=("watch-post",),
    )

    result = await collect_audience_intelligence(
        AudienceCollectionRequest(
            platform=SearchPlatform.DOUYIN,
            account_id=source.profile.account_id,
            account_url=source.profile.canonical_url,
            source_account_snapshot_sha256=canonical_sha256(source.model_dump(mode="json")),
            datasets=(AudienceDataset.CONTENT_INTERACTIONS,),
            session_ref="local-daneng",
            max_interactions=20,
        ),
        adapter=adapter,
        credential_provider=_provider(tmp_path),
    )

    assert result.status is AudienceCollectionStatus.FAILED
    assert result.interactions == ()
    assert RAW_ACTOR_ID not in result.model_dump_json()


@pytest.mark.asyncio
async def test_adapter_accepts_an_ordered_attempted_prefix_when_the_interaction_cap_is_reached(
    tmp_path: Path,
) -> None:
    source = _source()
    runner = _Runner(
        DouyinCommentCapture(
            captured_at=NOW + timedelta(hours=1),
            attempted_post_ids=("watch-post",),
            comments=(
                RawDouyinComment(
                    comment_id="comment-1",
                    post_id="watch-post",
                    raw_actor_id=RAW_ACTOR_ID,
                    text="只访问了第一条作品",
                    occurred_at=NOW,
                ),
            ),
            limitations=("The interaction cap was reached before every selected post was visited.",),
        )
    )
    adapter = DouyinAuthenticatedAudienceAdapter(
        source=source,
        runner=runner,
        local_actor_salt="local-only-pseudonym-salt",
        post_ids=("watch-post", "declutter-post"),
    )

    result = await collect_audience_intelligence(
        AudienceCollectionRequest(
            platform=SearchPlatform.DOUYIN,
            account_id=source.profile.account_id,
            account_url=source.profile.canonical_url,
            source_account_snapshot_sha256=canonical_sha256(source.model_dump(mode="json")),
            datasets=(AudienceDataset.CONTENT_INTERACTIONS,),
            session_ref="local-daneng",
            max_interactions=1,
        ),
        adapter=adapter,
        credential_provider=_provider(tmp_path),
    )

    assert result.status is AudienceCollectionStatus.PARTIAL
    assert len(result.interactions) == 1
    assert any("cap was reached" in item for item in result.limitations)


@pytest.mark.asyncio
async def test_adapter_does_not_open_posts_when_content_interactions_were_not_requested() -> None:
    source = _source()
    adapter = DouyinAuthenticatedAudienceAdapter(
        source=source,
        runner=_MustNotRun(),
        local_actor_salt="local-only-pseudonym-salt",
        post_ids=("watch-post",),
    )

    result = await adapter.collect(
        request=AudienceCollectionRequest(
            platform=SearchPlatform.DOUYIN,
            account_id=source.profile.account_id,
            account_url=source.profile.canonical_url,
            source_account_snapshot_sha256=canonical_sha256(source.model_dump(mode="json")),
            datasets=(AudienceDataset.ACCOUNT_SCALE,),
        ),
        credentials=None,
    )

    assert result.status is AudienceCollectionStatus.SUCCESS
    assert result.source is AudienceCollectionSource.PUBLIC_PLATFORM
    assert result.authenticated is False
    assert result.interactions == ()


def test_comment_payload_parser_accepts_only_the_requested_post_and_detects_schema_drift() -> None:
    comments = parse_douyin_comment_payload(
        {
            "status_code": 0,
            "comments": [
                {
                    "cid": "comment-1",
                    "aweme_id": "watch-post",
                    "text": "有明确问题的互动",
                    "create_time": int(NOW.timestamp()),
                    "digg_count": 12,
                    "reply_comment_total": 3,
                    "user": {"sec_uid": RAW_ACTOR_ID},
                }
            ],
        },
        post_id="watch-post",
    )

    assert comments == (
        RawDouyinComment(
            comment_id="comment-1",
            post_id="watch-post",
            raw_actor_id=RAW_ACTOR_ID,
            text="有明确问题的互动",
            occurred_at=NOW,
            visible_like_count=12,
            visible_reply_count=3,
        ),
    )

    with pytest.raises(DouyinCommentPayloadError, match="schema"):
        parse_douyin_comment_payload(
            {"status_code": 0, "comments": {"unexpected": "shape"}},
            post_id="watch-post",
        )


@pytest.mark.asyncio
async def test_comment_loading_clicks_the_stable_douyin_control_before_text_fallback() -> None:
    class Locator:
        def __init__(self, selector: str, clicked: list[str]) -> None:
            self.selector = selector
            self.clicked = clicked
            self.first = self

        async def count(self) -> int:
            return int(self.selector == '[data-e2e="feed-comment-icon"]')

        async def is_visible(self) -> bool:
            return True

        async def click(self, *, timeout: int) -> None:
            assert timeout == 3_000
            self.clicked.append(self.selector)

    class Mouse:
        async def wheel(self, x: int, y: int) -> None:
            raise AssertionError(f"unexpected scroll fallback: {x}, {y}")

    class Page:
        def __init__(self) -> None:
            self.clicked: list[str] = []
            self.mouse = Mouse()

        def locator(self, selector: str) -> Locator:
            return Locator(selector, self.clicked)

    page = Page()

    assert await _trigger_comment_loading(page) is True
    assert page.clicked == ['[data-e2e="feed-comment-icon"]']

    with pytest.raises(DouyinCommentPayloadError, match="another post"):
        parse_douyin_comment_payload(
            {
                "status_code": 0,
                "comments": [
                    {
                        "cid": "foreign-comment",
                        "aweme_id": "foreign-post",
                        "text": "串线",
                        "user": {"sec_uid": RAW_ACTOR_ID},
                    }
                ],
            },
            post_id="watch-post",
        )
