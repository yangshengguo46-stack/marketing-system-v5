from __future__ import annotations

from collections import defaultdict

from .audience_collection import (
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
)
from .contracts import canonical_sha256
from .local_browser_credentials import LocalBrowserCredentials
from .source_snapshot import AccountSourceSnapshot

_PROFILE_METRICS = {
    "followers": "followers.total",
    "following": "following.total",
    "likes_received": "likes_received.total",
}
_CONTENT_METRICS = {
    "plays": "content.plays",
    "likes": "content.likes",
    "comments": "content.comments",
    "shares": "content.shares",
    "favorites": "content.favorites",
}


def _metric(
    *,
    source_sha256: str,
    dataset: AudienceDataset,
    metric_name: str,
    value: int | float,
    observed_at,
    evidence_refs: tuple[str, ...],
) -> AudienceMetricObservation:
    metric_id = f"observed-{canonical_sha256({'source': source_sha256, 'name': metric_name})}"
    return AudienceMetricObservation(
        metric_id=metric_id,
        dataset=dataset,
        metric_name=metric_name,
        value=float(value),
        unit=AudienceMetricUnit.COUNT,
        shape=AudienceMetricShape.STOCK,
        nature=AudienceMetricNature.OBSERVED,
        origin=AudienceMetricOrigin.PLATFORM_PUBLIC,
        observed_at=observed_at,
        captured_at=observed_at,
        evidence_refs=evidence_refs,
    )


class SourceSnapshotAudienceAdapter:
    """Create the public audience baseline already present in an account snapshot."""

    capability_version = "source-snapshot-audience-v1"

    def __init__(self, *, source: AccountSourceSnapshot) -> None:
        self._source = source
        self._source_sha256 = canonical_sha256(source.model_dump(mode="json"))

    def collect(
        self,
        *,
        request: AudienceCollectionRequest,
        credentials: LocalBrowserCredentials | None,
    ) -> AudienceCollectionSnapshot:
        del credentials
        if request.platform.value != self._source.profile.platform:
            raise ValueError("audience request platform does not match source snapshot")
        if request.account_id != self._source.profile.account_id:
            raise ValueError("audience request account does not match source snapshot")
        if request.source_account_snapshot_sha256 != self._source_sha256:
            raise ValueError("audience request hash does not match source snapshot")

        metrics: list[AudienceMetricObservation] = []
        for raw_name, metric_name in _PROFILE_METRICS.items():
            value = self._source.profile.public_metrics.get(raw_name)
            if value is None:
                continue
            metrics.append(
                _metric(
                    source_sha256=self._source_sha256,
                    dataset=AudienceDataset.ACCOUNT_SCALE,
                    metric_name=metric_name,
                    value=value,
                    observed_at=self._source.captured_at,
                    evidence_refs=(f"snapshot://{self._source_sha256}/profile",),
                )
            )
        if self._source.profile.visible_work_count is not None:
            metrics.append(
                _metric(
                    source_sha256=self._source_sha256,
                    dataset=AudienceDataset.ACCOUNT_SCALE,
                    metric_name="works.visible",
                    value=self._source.profile.visible_work_count,
                    observed_at=self._source.captured_at,
                    evidence_refs=(f"snapshot://{self._source_sha256}/profile",),
                )
            )

        content_totals: dict[str, float] = defaultdict(float)
        content_refs: dict[str, list[str]] = defaultdict(list)
        for post in self._source.posts:
            for raw_name, metric_name in _CONTENT_METRICS.items():
                value = post.public_metrics.get(raw_name)
                if value is None:
                    continue
                content_totals[metric_name] += float(value)
                content_refs[metric_name].append(f"snapshot://{self._source_sha256}/post/{post.post_id}")
        for metric_name, value in sorted(content_totals.items()):
            metrics.append(
                _metric(
                    source_sha256=self._source_sha256,
                    dataset=AudienceDataset.CONTENT_INTERACTIONS,
                    metric_name=metric_name,
                    value=value,
                    observed_at=self._source.captured_at,
                    evidence_refs=tuple(content_refs[metric_name]),
                )
            )

        counts = defaultdict(int)
        for metric in metrics:
            counts[metric.dataset] += 1
        coverage = []
        for dataset in request.datasets:
            count = counts[dataset]
            if count:
                coverage.append(
                    AudienceDatasetCoverage(
                        dataset=dataset,
                        status=AudienceDatasetStatus.COLLECTED,
                        record_count=count,
                        source=AudienceCollectionSource.PUBLIC_PLATFORM,
                    )
                )
            else:
                coverage.append(
                    AudienceDatasetCoverage(
                        dataset=dataset,
                        status=AudienceDatasetStatus.UNAVAILABLE,
                        record_count=0,
                        source=AudienceCollectionSource.PUBLIC_PLATFORM,
                        limitations=("This dataset was not present in the bounded public account snapshot.",),
                    )
                )
        requested_metrics = tuple(metric for metric in metrics if metric.dataset in request.datasets)
        collected_count = sum(item.status is AudienceDatasetStatus.COLLECTED for item in coverage)
        if collected_count == len(coverage):
            status = AudienceCollectionStatus.SUCCESS
        elif collected_count:
            status = AudienceCollectionStatus.PARTIAL
        else:
            status = AudienceCollectionStatus.UNAVAILABLE
        return AudienceCollectionSnapshot(
            platform=request.platform,
            account_id=request.account_id,
            source_account_snapshot_sha256=self._source_sha256,
            requested_datasets=request.datasets,
            status=status,
            source=AudienceCollectionSource.PUBLIC_PLATFORM,
            capability_version=self.capability_version,
            authenticated=False,
            coverage=tuple(coverage),
            metrics=requested_metrics,
            captured_at=self._source.captured_at,
            limitations=("Public post totals describe visible response to the sampled content, not person-level audience behavior.",),
        )


__all__ = ["SourceSnapshotAudienceAdapter"]
