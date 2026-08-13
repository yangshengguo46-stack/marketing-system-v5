from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from experiments.e15_account_evidence.account_audience import (
    AccountAudienceIntelligencePack,
    build_account_audience_intelligence_pack,
)
from experiments.e15_account_evidence.audience_collection import (
    AUDIENCE_INTELLIGENCE_DATASETS,
    AudienceCollectionRequest,
    AudienceCollectionSnapshot,
    AudienceCollectionSource,
    AudienceCollectionStatus,
    AudienceDataset,
    AudienceDatasetCoverage,
    AudienceDatasetStatus,
    AudienceMetricNature,
    AudienceMetricObservation,
    AudienceMetricOrigin,
    AudienceMetricShape,
    AudienceMetricUnit,
    collect_audience_intelligence,
    derive_longitudinal_audience_metrics,
)
from experiments.e15_account_evidence.audience_evidence import (
    AudienceInteractionKind,
    AudienceInteractionObservation,
)
from experiments.e15_account_evidence.audience_snapshot_adapter import (
    SourceSnapshotAudienceAdapter,
)
from experiments.e15_account_evidence.contracts import SourceRights, canonical_sha256
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

NOW = datetime(2026, 8, 13, 14, 0, tzinfo=UTC)
COOKIE_SECRET = "audience-cookie-stays-local"


def _source_snapshot() -> AccountSourceSnapshot:
    return AccountSourceSnapshot(
        profile=AccountProfileObservation(
            platform="douyin",
            account_id="watch-account",
            canonical_url="https://www.douyin.com/user/watch-account",
            display_name="腕表账号",
            visible_work_count=2,
            public_metrics={"followers": 2_400, "likes_received": 16_000},
            captured_at=NOW,
        ),
        posts=(
            PostListObservation(
                post_id="post-1",
                canonical_url="https://www.douyin.com/video/post-1",
                caption="机械表与石英表",
                captured_at=NOW,
                public_metrics={"comments": 12, "likes": 120},
            ),
            PostListObservation(
                post_id="post-2",
                canonical_url="https://www.douyin.com/video/post-2",
                caption="腕表品牌历史",
                captured_at=NOW,
                public_metrics={"comments": 8, "likes": 80},
            ),
        ),
        collection_method=CollectionMethod.VISIBLE_BROWSER_AUTHORIZED,
        source_rights=SourceRights.ANALYSIS_ONLY,
        rights_ref="rights://comparison/watch-account",
        requested_url="https://www.douyin.com/user/watch-account",
        sample_basis="Bounded account sample.",
        captured_at=NOW,
    )


def _observed_metric(
    *,
    metric_id: str,
    metric_name: str,
    value: float,
    captured_at: datetime,
    dataset: AudienceDataset = AudienceDataset.ACCOUNT_SCALE,
) -> AudienceMetricObservation:
    return AudienceMetricObservation(
        metric_id=metric_id,
        dataset=dataset,
        metric_name=metric_name,
        value=value,
        unit=AudienceMetricUnit.COUNT,
        shape=AudienceMetricShape.STOCK,
        nature=AudienceMetricNature.OBSERVED,
        origin=AudienceMetricOrigin.PLATFORM_PUBLIC,
        observed_at=captured_at,
        captured_at=captured_at,
        evidence_refs=(f"platform://douyin/{metric_id}",),
    )


def _coverage(
    dataset: AudienceDataset,
    *,
    status: AudienceDatasetStatus = AudienceDatasetStatus.COLLECTED,
    record_count: int = 1,
) -> AudienceDatasetCoverage:
    return AudienceDatasetCoverage(
        dataset=dataset,
        status=status,
        record_count=record_count,
        source=AudienceCollectionSource.PUBLIC_PLATFORM,
        limitations=() if status is AudienceDatasetStatus.COLLECTED else ("Not fully visible.",),
    )


def _collection_snapshot(
    *,
    captured_at: datetime = NOW,
    follower_count: int = 1_000,
    interactions: tuple[AudienceInteractionObservation, ...] = (),
) -> AudienceCollectionSnapshot:
    source = _source_snapshot()
    source_sha = canonical_sha256(source.model_dump(mode="json"))
    requested = (
        AudienceDataset.ACCOUNT_SCALE,
        AudienceDataset.CONTENT_INTERACTIONS,
    )
    effective_captured_at = max(
        (interaction.captured_at for interaction in interactions),
        default=captured_at,
    )
    return AudienceCollectionSnapshot(
        platform=SearchPlatform.DOUYIN,
        account_id="watch-account",
        source_account_snapshot_sha256=source_sha,
        requested_datasets=requested,
        status=(AudienceCollectionStatus.SUCCESS if interactions else AudienceCollectionStatus.PARTIAL),
        source=AudienceCollectionSource.PUBLIC_PLATFORM,
        capability_version="fixture-audience-v1",
        authenticated=False,
        coverage=(
            _coverage(AudienceDataset.ACCOUNT_SCALE),
            _coverage(
                AudienceDataset.CONTENT_INTERACTIONS,
                status=(AudienceDatasetStatus.COLLECTED if interactions else AudienceDatasetStatus.UNAVAILABLE),
                record_count=len(interactions),
            ),
        ),
        metrics=(
            _observed_metric(
                metric_id=f"followers-{int(captured_at.timestamp())}",
                metric_name="followers.total",
                value=follower_count,
                captured_at=captured_at,
            ),
        ),
        interactions=interactions,
        captured_at=effective_captured_at,
    )


def test_audience_intelligence_datasets_cover_chanmama_style_account_observation() -> None:
    assert AUDIENCE_INTELLIGENCE_DATASETS == (
        AudienceDataset.ACCOUNT_SCALE,
        AudienceDataset.GROWTH_HISTORY,
        AudienceDataset.FOLLOWER_DEMOGRAPHICS,
        AudienceDataset.AUDIENCE_INTERESTS,
        AudienceDataset.AUDIENCE_ACTIVITY,
        AudienceDataset.CONTENT_INTERACTIONS,
        AudienceDataset.LIVE_AUDIENCE,
        AudienceDataset.COMMERCE_AFFINITY,
    )


@pytest.mark.asyncio
async def test_source_snapshot_adapter_builds_public_audience_baseline_without_inventing_gaps() -> None:
    source = _source_snapshot()
    source_sha256 = canonical_sha256(source.model_dump(mode="json"))

    result = await collect_audience_intelligence(
        AudienceCollectionRequest(
            platform=SearchPlatform.DOUYIN,
            account_id="watch-account",
            account_url="https://www.douyin.com/user/watch-account",
            source_account_snapshot_sha256=source_sha256,
        ),
        adapter=SourceSnapshotAudienceAdapter(source=source),
    )

    coverage = {item.dataset: item for item in result.coverage}
    assert result.status is AudienceCollectionStatus.PARTIAL
    assert coverage[AudienceDataset.ACCOUNT_SCALE].status is AudienceDatasetStatus.COLLECTED
    assert coverage[AudienceDataset.CONTENT_INTERACTIONS].status is AudienceDatasetStatus.COLLECTED
    assert coverage[AudienceDataset.FOLLOWER_DEMOGRAPHICS].status is AudienceDatasetStatus.UNAVAILABLE
    assert {metric.metric_name for metric in result.metrics} >= {
        "followers.total",
        "likes_received.total",
        "works.visible",
        "content.comments",
        "content.likes",
    }
    assert all(metric.nature is AudienceMetricNature.OBSERVED for metric in result.metrics)
    assert result.interactions == ()


def test_snapshot_rejects_metrics_for_a_dataset_reported_unavailable() -> None:
    snapshot = _collection_snapshot()

    with pytest.raises(ValidationError, match="unavailable audience dataset"):
        AudienceCollectionSnapshot.model_validate(
            snapshot.model_copy(
                update={
                    "coverage": (
                        _coverage(
                            AudienceDataset.ACCOUNT_SCALE,
                            status=AudienceDatasetStatus.UNAVAILABLE,
                            record_count=0,
                        ),
                        snapshot.coverage[1],
                    )
                }
            ).model_dump()
        )


def test_collection_snapshot_requires_explicit_coverage_for_every_requested_dataset() -> None:
    snapshot = _collection_snapshot()

    with pytest.raises(ValidationError, match="coverage"):
        AudienceCollectionSnapshot.model_validate(snapshot.model_copy(update={"coverage": snapshot.coverage[:1]}).model_dump())


def test_observed_computed_and_estimated_metrics_cannot_impersonate_each_other() -> None:
    observed = _observed_metric(
        metric_id="followers-now",
        metric_name="followers.total",
        value=1_000,
        captured_at=NOW,
    )

    with pytest.raises(ValidationError, match="observed metric"):
        AudienceMetricObservation.model_validate(observed.model_copy(update={"origin": AudienceMetricOrigin.MODEL_ESTIMATE}).model_dump())

    with pytest.raises(ValidationError, match="estimated metric"):
        AudienceMetricObservation.model_validate(
            observed.model_copy(
                update={
                    "nature": AudienceMetricNature.ESTIMATED,
                    "origin": AudienceMetricOrigin.MODEL_ESTIMATE,
                }
            ).model_dump()
        )


def test_longitudinal_snapshots_derive_growth_without_relabeling_it_observed() -> None:
    previous = _collection_snapshot(captured_at=NOW, follower_count=1_000)
    current = _collection_snapshot(
        captured_at=NOW + timedelta(days=1),
        follower_count=1_120,
    )

    derived = derive_longitudinal_audience_metrics(previous=previous, current=current)

    assert len(derived) == 1
    assert derived[0].dataset is AudienceDataset.GROWTH_HISTORY
    assert derived[0].metric_name == "followers.total.net_change"
    assert derived[0].value == 120
    assert derived[0].nature is AudienceMetricNature.DERIVED
    assert derived[0].origin is AudienceMetricOrigin.LOCAL_LONGITUDINAL
    assert derived[0].source_metric_ids == (
        previous.metrics[0].metric_id,
        current.metrics[0].metric_id,
    )


def test_longitudinal_growth_never_uses_estimated_follower_values() -> None:
    previous = _collection_snapshot(captured_at=NOW, follower_count=1_000)
    estimated_metric = AudienceMetricObservation.model_validate(
        previous.metrics[0]
        .model_copy(
            update={
                "nature": AudienceMetricNature.ESTIMATED,
                "origin": AudienceMetricOrigin.THIRD_PARTY_ESTIMATE,
                "evidence_refs": (),
                "estimate_method": "Third-party public estimate.",
            }
        )
        .model_dump()
    )
    estimated_previous = AudienceCollectionSnapshot.model_validate(previous.model_copy(update={"metrics": (estimated_metric,)}).model_dump())
    current = _collection_snapshot(
        captured_at=NOW + timedelta(days=1),
        follower_count=1_120,
    )

    assert (
        derive_longitudinal_audience_metrics(
            previous=estimated_previous,
            current=current,
        )
        == ()
    )


@pytest.mark.asyncio
async def test_audience_collection_uses_local_login_state_without_returning_cookie(
    tmp_path: Path,
) -> None:
    storage_state = tmp_path / "douyin-account.json"
    storage_state.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )
    provider = LocalBrowserCredentialProvider({(SearchPlatform.DOUYIN, "account-a"): storage_state})

    class Adapter:
        async def collect(self, *, request, credentials):
            assert credentials.playwright_storage_state()["cookies"][0]["value"] == COOKIE_SECRET
            snapshot = _collection_snapshot()
            return snapshot.model_copy(
                update={
                    "requested_datasets": request.datasets,
                    "authenticated": True,
                    "source": AudienceCollectionSource.AUTHENTICATED_PLATFORM,
                }
            )

    result = await collect_audience_intelligence(
        AudienceCollectionRequest(
            platform=SearchPlatform.DOUYIN,
            account_id="watch-account",
            account_url="https://www.douyin.com/user/watch-account",
            source_account_snapshot_sha256=_collection_snapshot().source_account_snapshot_sha256,
            datasets=(
                AudienceDataset.ACCOUNT_SCALE,
                AudienceDataset.CONTENT_INTERACTIONS,
            ),
            session_ref="account-a",
        ),
        adapter=Adapter(),
        credential_provider=provider,
    )

    assert result.authenticated is True
    assert COOKIE_SECRET not in result.model_dump_json()


def test_account_pack_builds_audience_sequences_from_interaction_samples_not_comments_module() -> None:
    interactions = (
        AudienceInteractionObservation.from_raw_actor(
            interaction_id="interaction-2",
            platform="douyin",
            account_id="watch-account",
            item_id="post-2",
            item_text="腕表品牌历史",
            kind=AudienceInteractionKind.COMMENT,
            raw_actor_id="viewer-a",
            local_salt="local-account-secret",
            text="这个品牌最早是怎么来的？",
            occurred_at=NOW + timedelta(minutes=2),
            captured_at=NOW + timedelta(hours=1),
            evidence_ref="interaction://douyin/interaction-2",
        ),
        AudienceInteractionObservation.from_raw_actor(
            interaction_id="interaction-1",
            platform="douyin",
            account_id="watch-account",
            item_id="post-1",
            item_text="机械表与石英表",
            kind=AudienceInteractionKind.COMMENT,
            raw_actor_id="viewer-a",
            local_salt="local-account-secret",
            text="日常通勤哪个更省心？",
            occurred_at=NOW + timedelta(minutes=1),
            captured_at=NOW + timedelta(hours=1),
            evidence_ref="interaction://douyin/interaction-1",
        ),
    )
    source = _source_snapshot()
    collection = _collection_snapshot(interactions=interactions)

    pack = build_account_audience_intelligence_pack(
        source=source,
        collection_snapshots=(collection,),
        generated_at=NOW + timedelta(hours=2),
    )

    assert isinstance(pack, AccountAudienceIntelligencePack)
    assert pack.collection_snapshot_count == 1
    assert pack.behavior_sequence_count == 1
    assert [event.event_id for event in pack.behavior_sequences[0].events] == [
        "interaction-1",
        "interaction-2",
    ]
    assert "viewer-a" not in pack.model_dump_json()
    persisted = AudienceCollectionSnapshot.model_validate_json(collection.model_dump_json())
    assert persisted.interactions[0].actor_ref.startswith("actor://sha256/")
    assert pack.hllm_profile_count == 0


def test_account_pack_rejects_interactions_for_posts_outside_the_account_snapshot() -> None:
    interaction = AudienceInteractionObservation.from_raw_actor(
        interaction_id="interaction-unknown",
        platform="douyin",
        account_id="watch-account",
        item_id="post-not-in-snapshot",
        item_text="未知作品",
        kind=AudienceInteractionKind.COMMENT,
        raw_actor_id="viewer-a",
        local_salt="local-account-secret",
        text="评论",
        occurred_at=NOW,
        captured_at=NOW + timedelta(hours=1),
        evidence_ref="interaction://douyin/unknown",
    )

    with pytest.raises(ValueError, match="outside the account snapshot"):
        build_account_audience_intelligence_pack(
            source=_source_snapshot(),
            collection_snapshots=(_collection_snapshot(interactions=(interaction,)),),
            generated_at=NOW + timedelta(hours=2),
        )
