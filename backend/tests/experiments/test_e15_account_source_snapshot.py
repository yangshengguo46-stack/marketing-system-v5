from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from experiments.e15_account_evidence.contracts import SourceRights
from experiments.e15_account_evidence.source_snapshot import (
    AccountProfileObservation,
    AccountSourceSnapshot,
    CollectionMethod,
    PostListObservation,
    cache_account_source_snapshot,
)

NOW = datetime(2026, 8, 13, 8, 0, tzinfo=UTC)


def _snapshot(*, caption: str = "腕表与人的故事") -> AccountSourceSnapshot:
    return AccountSourceSnapshot(
        profile=AccountProfileObservation(
            platform="douyin",
            account_id="public-account-1",
            canonical_url="https://www.douyin.com/user/public-account-1",
            display_name="示例账号",
            bio="公开主页简介",
            visible_work_count=572,
            captured_at=NOW,
        ),
        posts=(
            PostListObservation(
                post_id="post-1",
                canonical_url="https://www.douyin.com/video/post-1",
                caption=caption,
                captured_at=NOW,
                public_metrics={"likes": 4832},
            ),
        ),
        collection_method=CollectionMethod.MANUAL_PUBLIC_OBSERVATION,
        source_rights=SourceRights.ANALYSIS_ONLY,
        rights_ref="request://user-supplied-link/2026-08-13",
        requested_url="https://v.douyin.com/example/",
        sample_basis="One user-requested public profile viewport; no automated expansion.",
        captured_at=NOW,
        limitations=("Only the visible public sample was captured.",),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cookies", {"session": "secret"}),
        ("local_storage", {"token": "secret"}),
        ("raw_html", "<html>full page</html>"),
        ("temporary_media_url", "https://temporary.example/video.mp4"),
    ],
)
def test_snapshot_contract_rejects_browser_secrets_and_raw_page_payloads(field: str, value: object) -> None:
    payload = _snapshot().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AccountSourceSnapshot.model_validate(payload)


def test_post_contract_accepts_only_stable_artifact_handles() -> None:
    payload = _snapshot().posts[0].model_dump()
    payload["media_artifact_ref"] = "https://temporary.example/video.mp4?expires=1"

    with pytest.raises(ValidationError, match="artifact://"):
        PostListObservation.model_validate(payload)


def test_content_addressed_snapshot_cache_reuses_identical_capture(tmp_path: Path) -> None:
    first = cache_account_source_snapshot(_snapshot(), cache_root=tmp_path)
    second = cache_account_source_snapshot(_snapshot(), cache_root=tmp_path)

    assert first.snapshot_sha256 == second.snapshot_sha256
    assert first.path == second.path
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert len(list(tmp_path.rglob("snapshot.json"))) == 1

    persisted = json.loads(first.path.read_text(encoding="utf-8"))
    encoded = json.dumps(persisted, ensure_ascii=False)
    assert "secret" not in encoded
    assert "raw_html" not in encoded


def test_snapshot_cache_key_changes_when_observed_content_changes(tmp_path: Path) -> None:
    first = cache_account_source_snapshot(_snapshot(), cache_root=tmp_path)
    changed = cache_account_source_snapshot(_snapshot(caption="腕表与汽车的生活记录"), cache_root=tmp_path)

    assert first.snapshot_sha256 != changed.snapshot_sha256
    assert first.path != changed.path
