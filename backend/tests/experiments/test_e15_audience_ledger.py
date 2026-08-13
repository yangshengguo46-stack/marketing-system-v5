from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from experiments.e15_account_evidence.audience_collection import (
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
)
from experiments.e15_account_evidence.audience_ledger import (
    AudienceLedgerIntegrityError,
    append_audience_snapshot,
    load_audience_history,
)
from experiments.e15_account_evidence.platform_search import SearchPlatform

NOW = datetime(2026, 8, 13, 16, 0, tzinfo=UTC)


def _snapshot(*, captured_at: datetime, followers: int) -> AudienceCollectionSnapshot:
    metric_id = f"followers-{int(captured_at.timestamp())}"
    return AudienceCollectionSnapshot(
        platform=SearchPlatform.DOUYIN,
        account_id="watch-account",
        source_account_snapshot_sha256="a" * 64,
        requested_datasets=(AudienceDataset.ACCOUNT_SCALE,),
        status=AudienceCollectionStatus.SUCCESS,
        source=AudienceCollectionSource.PUBLIC_PLATFORM,
        capability_version="fixture-v1",
        authenticated=False,
        coverage=(
            AudienceDatasetCoverage(
                dataset=AudienceDataset.ACCOUNT_SCALE,
                status=AudienceDatasetStatus.COLLECTED,
                record_count=1,
                source=AudienceCollectionSource.PUBLIC_PLATFORM,
            ),
        ),
        metrics=(
            AudienceMetricObservation(
                metric_id=metric_id,
                dataset=AudienceDataset.ACCOUNT_SCALE,
                metric_name="followers.total",
                value=followers,
                unit=AudienceMetricUnit.COUNT,
                shape=AudienceMetricShape.STOCK,
                nature=AudienceMetricNature.OBSERVED,
                origin=AudienceMetricOrigin.PLATFORM_PUBLIC,
                observed_at=captured_at,
                captured_at=captured_at,
                evidence_refs=(f"platform://douyin/{metric_id}",),
            ),
        ),
        captured_at=captured_at,
    )


def test_audience_ledger_is_append_only_idempotent_and_chronological(tmp_path) -> None:
    later = _snapshot(captured_at=NOW + timedelta(days=1), followers=1_120)
    earlier = _snapshot(captured_at=NOW, followers=1_000)

    first = append_audience_snapshot(later, ledger_root=tmp_path)
    second = append_audience_snapshot(earlier, ledger_root=tmp_path)
    duplicate = append_audience_snapshot(earlier, ledger_root=tmp_path)
    history = load_audience_history(
        platform=SearchPlatform.DOUYIN,
        account_id="watch-account",
        ledger_root=tmp_path,
    )

    assert first.created is True
    assert second.created is True
    assert duplicate.created is False
    assert duplicate.snapshot_sha256 == second.snapshot_sha256
    assert [item.captured_at for item in history.snapshots] == [
        NOW,
        NOW + timedelta(days=1),
    ]
    assert history.derived_metrics[0].metric_name == "followers.total.net_change"
    assert history.derived_metrics[0].value == 120


def test_audience_ledger_detects_tampered_snapshot(tmp_path) -> None:
    result = append_audience_snapshot(
        _snapshot(captured_at=NOW, followers=1_000),
        ledger_root=tmp_path,
    )
    payload = json.loads(result.path.read_text(encoding="utf-8"))
    payload["metrics"][0]["value"] = 999
    result.path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AudienceLedgerIntegrityError, match="hash"):
        load_audience_history(
            platform=SearchPlatform.DOUYIN,
            account_id="watch-account",
            ledger_root=tmp_path,
        )


def test_audience_ledger_keeps_same_time_evidence_without_zero_window_growth(
    tmp_path,
) -> None:
    append_audience_snapshot(
        _snapshot(captured_at=NOW, followers=1_000),
        ledger_root=tmp_path,
    )
    append_audience_snapshot(
        _snapshot(captured_at=NOW, followers=1_001),
        ledger_root=tmp_path,
    )

    history = load_audience_history(
        platform=SearchPlatform.DOUYIN,
        account_id="watch-account",
        ledger_root=tmp_path,
    )

    assert len(history.snapshots) == 2
    assert history.derived_metrics == ()


def test_audience_ledger_account_paths_do_not_embed_raw_account_ids(tmp_path) -> None:
    result = append_audience_snapshot(
        _snapshot(captured_at=NOW, followers=1_000).model_copy(update={"account_id": "user/unsafe?raw=id"}),
        ledger_root=tmp_path,
    )

    assert "user/unsafe?raw=id" not in str(result.path)
