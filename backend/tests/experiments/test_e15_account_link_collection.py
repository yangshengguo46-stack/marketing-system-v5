from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from experiments.e15_account_evidence.account_link_collection import (
    AccountLinkCollectionRequest,
    StructuredAccountObservation,
    collect_account_link,
)
from experiments.e15_account_evidence.contracts import SourceRights
from experiments.e15_account_evidence.source_snapshot import (
    AccountProfileObservation,
    CollectionMethod,
    PostListObservation,
)

NOW = datetime(2026, 8, 13, 8, 0, tzinfo=UTC)


def _request(tmp_path: Path, *, max_posts: int = 12) -> AccountLinkCollectionRequest:
    return AccountLinkCollectionRequest(
        requested_url="https://v.douyin.com/example/",
        collection_method=CollectionMethod.VISIBLE_BROWSER_AUTHORIZED,
        source_rights=SourceRights.ANALYSIS_ONLY,
        rights_ref="request://user-supplied-link/2026-08-13",
        max_posts=max_posts,
        cache_root=tmp_path,
    )


def _observation(post_count: int = 2) -> StructuredAccountObservation:
    return StructuredAccountObservation(
        profile=AccountProfileObservation(
            platform="douyin",
            account_id="public-account-1",
            canonical_url="https://www.douyin.com/user/public-account-1",
            display_name="示例账号",
            bio="公开简介",
            visible_work_count=572,
            captured_at=NOW,
        ),
        posts=tuple(
            PostListObservation(
                post_id=f"post-{index}",
                canonical_url=f"https://www.douyin.com/video/post-{index}",
                caption=f"作品 {index}",
                captured_at=NOW,
                public_metrics={"likes": index},
            )
            for index in range(post_count)
        ),
        final_url="https://www.douyin.com/user/public-account-1",
        sample_basis="Visible works returned by the bounded local browser collection.",
        captured_at=NOW,
        limitations=("No private browser state was read.",),
    )


@pytest.mark.asyncio
async def test_link_collection_passes_only_url_and_bound_to_local_collector(tmp_path: Path) -> None:
    calls: list[tuple[str, int]] = []

    async def collector(*, requested_url: str, max_posts: int) -> StructuredAccountObservation:
        calls.append((requested_url, max_posts))
        return _observation()

    result = await collect_account_link(_request(tmp_path), collector=collector)

    assert calls == [("https://v.douyin.com/example/", 12)]
    assert result.snapshot.profile.account_id == "public-account-1"
    assert result.snapshot.requested_url == "https://v.douyin.com/example/"
    assert result.cache.path.is_file()


@pytest.mark.asyncio
async def test_link_collection_rejects_collector_that_exceeds_requested_sample(tmp_path: Path) -> None:
    async def collector(**_kwargs) -> StructuredAccountObservation:
        return _observation(post_count=13)

    with pytest.raises(ValueError, match="exceeded max_posts"):
        await collect_account_link(_request(tmp_path), collector=collector)

    assert not list(tmp_path.rglob("snapshot.json"))


def test_structured_observation_rejects_raw_dom_and_browser_storage() -> None:
    payload = _observation().model_dump()
    payload["raw_dom"] = "<body>all content</body>"
    payload["cookies"] = {"session": "secret"}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StructuredAccountObservation.model_validate(payload)


def test_link_collection_request_has_a_small_explicit_sample_cap(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="less than or equal to 24"):
        _request(tmp_path, max_posts=25)
