from __future__ import annotations

import inspect
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import Any, Protocol
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from .audience_evidence import AudienceInteractionObservation
from .contracts import StrictModel, canonical_sha256
from .local_browser_credentials import (
    InvalidLocalBrowserCredential,
    LocalBrowserCredentialNotFound,
    LocalBrowserCredentialProvider,
    LocalBrowserCredentials,
)
from .platform_search import SearchPlatform


class AudienceDataset(StrEnum):
    ACCOUNT_SCALE = "account_scale"
    GROWTH_HISTORY = "growth_history"
    FOLLOWER_DEMOGRAPHICS = "follower_demographics"
    AUDIENCE_INTERESTS = "audience_interests"
    AUDIENCE_ACTIVITY = "audience_activity"
    CONTENT_INTERACTIONS = "content_interactions"
    LIVE_AUDIENCE = "live_audience"
    COMMERCE_AFFINITY = "commerce_affinity"


AUDIENCE_INTELLIGENCE_DATASETS = (
    AudienceDataset.ACCOUNT_SCALE,
    AudienceDataset.GROWTH_HISTORY,
    AudienceDataset.FOLLOWER_DEMOGRAPHICS,
    AudienceDataset.AUDIENCE_INTERESTS,
    AudienceDataset.AUDIENCE_ACTIVITY,
    AudienceDataset.CONTENT_INTERACTIONS,
    AudienceDataset.LIVE_AUDIENCE,
    AudienceDataset.COMMERCE_AFFINITY,
)


class AudienceCollectionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NEEDS_LOGIN = "needs_login"
    RESTRICTED = "restricted"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    SCHEMA_DRIFT = "schema_drift"


class AudienceDatasetStatus(StrEnum):
    COLLECTED = "collected"
    PARTIAL = "partial"
    NEEDS_LOGIN = "needs_login"
    RESTRICTED = "restricted"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    SCHEMA_DRIFT = "schema_drift"


class AudienceCollectionSource(StrEnum):
    PUBLIC_PLATFORM = "public_platform"
    AUTHENTICATED_PLATFORM = "authenticated_platform"
    CREATOR_DASHBOARD = "creator_dashboard"
    USER_EXPORT = "user_export"
    LONGITUDINAL_OBSERVATION = "longitudinal_observation"
    THIRD_PARTY_DATA = "third_party_data"
    UNKNOWN = "unknown"


class AudienceMetricNature(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    ESTIMATED = "estimated"


class AudienceMetricOrigin(StrEnum):
    PLATFORM_PUBLIC = "platform_public"
    PLATFORM_AUTHENTICATED = "platform_authenticated"
    CREATOR_DASHBOARD = "creator_dashboard"
    USER_EXPORT = "user_export"
    LOCAL_LONGITUDINAL = "local_longitudinal"
    THIRD_PARTY_OBSERVED = "third_party_observed"
    THIRD_PARTY_ESTIMATE = "third_party_estimate"
    MODEL_ESTIMATE = "model_estimate"


class AudienceMetricUnit(StrEnum):
    COUNT = "count"
    RATIO = "ratio"
    INDEX = "index"
    CURRENCY_MINOR = "currency_minor"
    SECONDS = "seconds"


class AudienceMetricShape(StrEnum):
    STOCK = "stock"
    FLOW = "flow"
    DISTRIBUTION = "distribution"
    RATE = "rate"
    RANK = "rank"


_OBSERVED_ORIGINS = {
    AudienceMetricOrigin.PLATFORM_PUBLIC,
    AudienceMetricOrigin.PLATFORM_AUTHENTICATED,
    AudienceMetricOrigin.CREATOR_DASHBOARD,
    AudienceMetricOrigin.USER_EXPORT,
    AudienceMetricOrigin.THIRD_PARTY_OBSERVED,
}
_ESTIMATED_ORIGINS = {
    AudienceMetricOrigin.THIRD_PARTY_ESTIMATE,
    AudienceMetricOrigin.MODEL_ESTIMATE,
}


def _aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _absolute_http_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("account_url must be an absolute http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("account_url must not contain credentials")
    return value


class AudienceCollectionRequest(StrictModel):
    platform: SearchPlatform
    account_id: str = Field(min_length=1, max_length=500)
    account_url: str = Field(min_length=1, max_length=2_000)
    source_account_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    datasets: tuple[AudienceDataset, ...] = AUDIENCE_INTELLIGENCE_DATASETS
    session_ref: str | None = Field(default=None, min_length=1, max_length=240)
    max_interactions: int = Field(default=500, ge=1, le=5_000)

    @field_validator("account_url")
    @classmethod
    def validate_account_url(cls, value: str) -> str:
        return _absolute_http_url(value)

    @model_validator(mode="after")
    def validate_datasets(self) -> AudienceCollectionRequest:
        if not self.datasets:
            raise ValueError("at least one audience dataset is required")
        if len(set(self.datasets)) != len(self.datasets):
            raise ValueError("audience datasets must be unique")
        return self


class AudienceDatasetCoverage(StrictModel):
    dataset: AudienceDataset
    status: AudienceDatasetStatus
    record_count: int = Field(ge=0)
    source: AudienceCollectionSource
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 1_200 for item in value):
            raise ValueError("limitations must be non-empty and at most 1200 characters")
        return value

    @model_validator(mode="after")
    def validate_coverage(self) -> AudienceDatasetCoverage:
        if (
            self.status
            not in {
                AudienceDatasetStatus.COLLECTED,
                AudienceDatasetStatus.PARTIAL,
            }
            and self.record_count
        ):
            raise ValueError("unavailable audience dataset cannot report records")
        if self.status is not AudienceDatasetStatus.COLLECTED and not self.limitations:
            raise ValueError("non-collected audience dataset requires a limitation")
        return self


class AudienceMetricObservation(StrictModel):
    metric_id: str = Field(min_length=1, max_length=500)
    dataset: AudienceDataset
    metric_name: str = Field(min_length=1, max_length=240)
    value: float
    unit: AudienceMetricUnit
    shape: AudienceMetricShape
    nature: AudienceMetricNature
    origin: AudienceMetricOrigin
    observed_at: datetime
    captured_at: datetime
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    source_metric_ids: tuple[str, ...] = Field(default_factory=tuple)
    estimate_method: str | None = Field(default=None, min_length=1, max_length=1_000)
    window_start: datetime | None = None
    window_end: datetime | None = None
    label: str | None = Field(default=None, max_length=500)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("audience metric value must be finite")
        return value

    @field_validator("observed_at", "captured_at", "window_start", "window_end")
    @classmethod
    def validate_timestamps(cls, value: datetime | None, info) -> datetime | None:
        if value is None:
            return None
        return _aware(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_provenance(self) -> AudienceMetricObservation:
        if self.captured_at < self.observed_at:
            raise ValueError("captured_at cannot precede observed_at")
        if self.window_end is not None and self.window_start is None:
            raise ValueError("window_end requires window_start")
        if self.window_start is not None and self.window_end is not None and self.window_end < self.window_start:
            raise ValueError("window_end cannot precede window_start")
        if self.unit is AudienceMetricUnit.RATIO and not 0 <= self.value <= 1:
            raise ValueError("ratio metric must be between 0 and 1")
        if self.nature is AudienceMetricNature.OBSERVED:
            if self.origin not in _OBSERVED_ORIGINS:
                raise ValueError("observed metric requires an observed origin")
            if not self.evidence_refs:
                raise ValueError("observed metric requires evidence refs")
            if self.source_metric_ids or self.estimate_method is not None:
                raise ValueError("observed metric cannot carry derivation or estimate metadata")
        elif self.nature is AudienceMetricNature.DERIVED:
            if self.origin is not AudienceMetricOrigin.LOCAL_LONGITUDINAL:
                raise ValueError("derived metric requires local longitudinal origin")
            if len(self.source_metric_ids) < 2:
                raise ValueError("derived metric requires at least two source metrics")
            if self.estimate_method is not None:
                raise ValueError("derived metric cannot carry an estimate method")
        elif self.nature is AudienceMetricNature.ESTIMATED:
            if self.origin not in _ESTIMATED_ORIGINS:
                raise ValueError("estimated metric requires an estimated origin")
            if not self.estimate_method:
                raise ValueError("estimated metric requires an estimate method")
        return self


class AudienceCollectionSnapshot(StrictModel):
    platform: SearchPlatform
    account_id: str = Field(min_length=1, max_length=500)
    source_account_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_datasets: tuple[AudienceDataset, ...]
    status: AudienceCollectionStatus
    source: AudienceCollectionSource
    capability_version: str = Field(min_length=1, max_length=240)
    authenticated: bool
    coverage: tuple[AudienceDatasetCoverage, ...]
    metrics: tuple[AudienceMetricObservation, ...] = Field(default_factory=tuple)
    interactions: tuple[AudienceInteractionObservation, ...] = Field(default_factory=tuple)
    captured_at: datetime
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    error_code: str | None = Field(default=None, max_length=160)
    error_message: str | None = Field(default=None, max_length=500)

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _aware(value, field_name="captured_at")

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 1_200 for item in value):
            raise ValueError("limitations must be non-empty and at most 1200 characters")
        return value

    @model_validator(mode="after")
    def validate_snapshot(self) -> AudienceCollectionSnapshot:
        if not self.requested_datasets or len(set(self.requested_datasets)) != len(self.requested_datasets):
            raise ValueError("requested audience datasets must be non-empty and unique")
        coverage_by_dataset = {item.dataset: item for item in self.coverage}
        if len(coverage_by_dataset) != len(self.coverage):
            raise ValueError("audience dataset coverage must be unique")
        if set(coverage_by_dataset) != set(self.requested_datasets):
            raise ValueError("coverage must exist for every requested audience dataset")
        if any(metric.dataset not in self.requested_datasets for metric in self.metrics):
            raise ValueError("audience metric belongs to an unrequested dataset")
        if any(coverage_by_dataset[metric.dataset].status not in {AudienceDatasetStatus.COLLECTED, AudienceDatasetStatus.PARTIAL} for metric in self.metrics):
            raise ValueError("unavailable audience dataset cannot carry metrics")
        if self.interactions and AudienceDataset.CONTENT_INTERACTIONS not in self.requested_datasets:
            raise ValueError("audience interactions require the content interactions dataset")
        if self.interactions and coverage_by_dataset[AudienceDataset.CONTENT_INTERACTIONS].status not in {
            AudienceDatasetStatus.COLLECTED,
            AudienceDatasetStatus.PARTIAL,
        }:
            raise ValueError("unavailable audience dataset cannot carry interactions")
        if any(interaction.platform != self.platform.value or interaction.account_id != self.account_id for interaction in self.interactions):
            raise ValueError("audience interaction crosses account boundary")
        if any(metric.captured_at > self.captured_at for metric in self.metrics):
            raise ValueError("audience metric cannot be captured after its snapshot")
        if any(interaction.captured_at > self.captured_at for interaction in self.interactions):
            raise ValueError("audience interaction cannot be captured after its snapshot")
        metric_ids = [metric.metric_id for metric in self.metrics]
        interaction_ids = [item.interaction_id for item in self.interactions]
        if len(set(metric_ids)) != len(metric_ids):
            raise ValueError("audience metric ids must be unique")
        if len(set(interaction_ids)) != len(interaction_ids):
            raise ValueError("audience interaction ids must be unique")
        if self.status is AudienceCollectionStatus.SUCCESS and any(item.status is not AudienceDatasetStatus.COLLECTED for item in self.coverage):
            raise ValueError("successful audience collection requires every dataset collected")
        if self.status not in {AudienceCollectionStatus.SUCCESS, AudienceCollectionStatus.PARTIAL} and (self.metrics or self.interactions):
            raise ValueError("failed audience collection cannot carry observations")
        return self


class AudienceCollectionAdapter(Protocol):
    def collect(
        self,
        *,
        request: AudienceCollectionRequest,
        credentials: LocalBrowserCredentials | None,
    ) -> object: ...


async def _await_if_needed(value: object) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _unavailable_snapshot(
    request: AudienceCollectionRequest,
    *,
    status: AudienceCollectionStatus,
    dataset_status: AudienceDatasetStatus,
    error_code: str,
    error_message: str,
) -> AudienceCollectionSnapshot:
    limitation = error_message
    return AudienceCollectionSnapshot(
        platform=request.platform,
        account_id=request.account_id,
        source_account_snapshot_sha256=request.source_account_snapshot_sha256,
        requested_datasets=request.datasets,
        status=status,
        source=AudienceCollectionSource.UNKNOWN,
        capability_version="unavailable-v1",
        authenticated=False,
        coverage=tuple(
            AudienceDatasetCoverage(
                dataset=dataset,
                status=dataset_status,
                record_count=0,
                source=AudienceCollectionSource.UNKNOWN,
                limitations=(limitation,),
            )
            for dataset in request.datasets
        ),
        captured_at=datetime.now(UTC),
        limitations=(limitation,),
        error_code=error_code,
        error_message=error_message,
    )


async def collect_audience_intelligence(
    request: AudienceCollectionRequest,
    *,
    adapter: AudienceCollectionAdapter,
    credential_provider: LocalBrowserCredentialProvider | None = None,
) -> AudienceCollectionSnapshot:
    credentials: LocalBrowserCredentials | None = None
    if request.session_ref is not None:
        if credential_provider is None:
            return _unavailable_snapshot(
                request,
                status=AudienceCollectionStatus.NEEDS_LOGIN,
                dataset_status=AudienceDatasetStatus.NEEDS_LOGIN,
                error_code="session_not_connected",
                error_message="The selected local audience session is not connected.",
            )
        try:
            credentials = credential_provider.load(request.platform, request.session_ref)
        except LocalBrowserCredentialNotFound:
            return _unavailable_snapshot(
                request,
                status=AudienceCollectionStatus.NEEDS_LOGIN,
                dataset_status=AudienceDatasetStatus.NEEDS_LOGIN,
                error_code="session_not_connected",
                error_message="The selected local audience session is not connected.",
            )
        except InvalidLocalBrowserCredential:
            return _unavailable_snapshot(
                request,
                status=AudienceCollectionStatus.FAILED,
                dataset_status=AudienceDatasetStatus.FAILED,
                error_code="invalid_local_session",
                error_message="The selected local audience session could not be loaded.",
            )
    try:
        raw = adapter.collect(request=request, credentials=credentials)
        snapshot = AudienceCollectionSnapshot.model_validate(await _await_if_needed(raw))
    except Exception:
        return _unavailable_snapshot(
            request,
            status=AudienceCollectionStatus.FAILED,
            dataset_status=AudienceDatasetStatus.FAILED,
            error_code="audience_collection_failed",
            error_message="The audience collector failed without exposing local browser data.",
        )
    if snapshot.platform is not request.platform or snapshot.account_id != request.account_id:
        raise ValueError("audience collector returned another account")
    if snapshot.source_account_snapshot_sha256 != request.source_account_snapshot_sha256:
        raise ValueError("audience collector returned another account snapshot")
    if snapshot.requested_datasets != request.datasets:
        raise ValueError("audience collector changed requested datasets")
    if len(snapshot.interactions) > request.max_interactions:
        raise ValueError("audience collector exceeded max_interactions")
    return snapshot


def _metric_by_name(
    snapshot: AudienceCollectionSnapshot,
    metric_name: str,
) -> AudienceMetricObservation | None:
    matches = [metric for metric in snapshot.metrics if metric.metric_name == metric_name and metric.nature is AudienceMetricNature.OBSERVED]
    if not matches:
        return None
    return max(matches, key=lambda metric: (metric.observed_at, metric.metric_id))


def derive_longitudinal_audience_metrics(
    *,
    previous: AudienceCollectionSnapshot,
    current: AudienceCollectionSnapshot,
) -> tuple[AudienceMetricObservation, ...]:
    if previous.platform is not current.platform or previous.account_id != current.account_id:
        raise ValueError("longitudinal snapshots must belong to one account")
    if previous.captured_at >= current.captured_at:
        raise ValueError("longitudinal snapshots must be ordered in time")
    result: list[AudienceMetricObservation] = []
    for metric_name in ("followers.total",):
        before = _metric_by_name(previous, metric_name)
        after = _metric_by_name(current, metric_name)
        if before is None or after is None:
            continue
        # A later audience-collection retry may reuse the same account-source
        # observation. It is additional collection evidence, not a new point in
        # the account growth series.
        if before.metric_id == after.metric_id or before.observed_at >= after.observed_at:
            continue
        source_ids = (before.metric_id, after.metric_id)
        payload = {
            "platform": current.platform.value,
            "account_id": current.account_id,
            "metric_name": f"{metric_name}.net_change",
            "source_metric_ids": source_ids,
            "window_start": previous.captured_at.isoformat(),
            "window_end": current.captured_at.isoformat(),
        }
        result.append(
            AudienceMetricObservation(
                metric_id=f"derived-{canonical_sha256(payload)}",
                dataset=AudienceDataset.GROWTH_HISTORY,
                metric_name=f"{metric_name}.net_change",
                value=after.value - before.value,
                unit=before.unit,
                shape=AudienceMetricShape.FLOW,
                nature=AudienceMetricNature.DERIVED,
                origin=AudienceMetricOrigin.LOCAL_LONGITUDINAL,
                observed_at=current.captured_at,
                captured_at=current.captured_at,
                source_metric_ids=source_ids,
                window_start=previous.captured_at,
                window_end=current.captured_at,
            )
        )
    return tuple(result)


__all__ = [
    "AUDIENCE_INTELLIGENCE_DATASETS",
    "AudienceCollectionAdapter",
    "AudienceCollectionRequest",
    "AudienceCollectionSnapshot",
    "AudienceCollectionSource",
    "AudienceCollectionStatus",
    "AudienceDataset",
    "AudienceDatasetCoverage",
    "AudienceDatasetStatus",
    "AudienceMetricNature",
    "AudienceMetricObservation",
    "AudienceMetricOrigin",
    "AudienceMetricShape",
    "AudienceMetricUnit",
    "collect_audience_intelligence",
    "derive_longitudinal_audience_metrics",
]
