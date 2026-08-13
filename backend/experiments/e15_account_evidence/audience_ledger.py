from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, model_validator

from .audience_collection import (
    AudienceCollectionSnapshot,
    AudienceMetricObservation,
    derive_longitudinal_audience_metrics,
)
from .contracts import StrictModel, canonical_sha256
from .platform_search import SearchPlatform


class AudienceLedgerIntegrityError(RuntimeError):
    """Raised when an audience snapshot no longer matches its content address."""


class AudienceHistory(StrictModel):
    platform: SearchPlatform
    account_id: str = Field(min_length=1, max_length=500)
    snapshots: tuple[AudienceCollectionSnapshot, ...] = Field(default_factory=tuple)
    derived_metrics: tuple[AudienceMetricObservation, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_history(self) -> AudienceHistory:
        if any(item.platform is not self.platform or item.account_id != self.account_id for item in self.snapshots):
            raise ValueError("audience history crosses account boundary")
        if tuple(sorted(self.snapshots, key=lambda item: item.captured_at)) != self.snapshots:
            raise ValueError("audience history snapshots must be chronological")
        if any(metric.nature.value != "derived" for metric in self.derived_metrics):
            raise ValueError("audience history derived_metrics must remain derived")
        return self


@dataclass(frozen=True, slots=True)
class AudienceLedgerAppendResult:
    snapshot_sha256: str
    path: Path
    created: bool


def _account_directory(
    *,
    platform: SearchPlatform,
    account_id: str,
    ledger_root: Path,
) -> Path:
    account_key = canonical_sha256({"platform": platform.value, "account_id": account_id})
    return ledger_root.expanduser().resolve() / platform.value / account_key


def append_audience_snapshot(
    snapshot: AudienceCollectionSnapshot,
    *,
    ledger_root: Path,
) -> AudienceLedgerAppendResult:
    payload = snapshot.model_dump(mode="json")
    snapshot_sha256 = canonical_sha256(payload)
    directory = _account_directory(
        platform=snapshot.platform,
        account_id=snapshot.account_id,
        ledger_root=ledger_root,
    )
    target = directory / f"{snapshot_sha256}.json"
    if target.is_file():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if canonical_sha256(existing) != snapshot_sha256:
            raise AudienceLedgerIntegrityError("existing audience snapshot hash mismatch")
        return AudienceLedgerAppendResult(
            snapshot_sha256=snapshot_sha256,
            path=target,
            created=False,
        )

    directory.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    try:
        temporary.replace(target)
    except OSError:
        temporary.unlink(missing_ok=True)
        if not target.is_file():
            raise
        existing = json.loads(target.read_text(encoding="utf-8"))
        if canonical_sha256(existing) != snapshot_sha256:
            raise AudienceLedgerIntegrityError("concurrent audience snapshot hash mismatch")
        return AudienceLedgerAppendResult(
            snapshot_sha256=snapshot_sha256,
            path=target,
            created=False,
        )
    return AudienceLedgerAppendResult(
        snapshot_sha256=snapshot_sha256,
        path=target,
        created=True,
    )


def load_audience_history(
    *,
    platform: SearchPlatform,
    account_id: str,
    ledger_root: Path,
) -> AudienceHistory:
    directory = _account_directory(
        platform=platform,
        account_id=account_id,
        ledger_root=ledger_root,
    )
    snapshots: list[AudienceCollectionSnapshot] = []
    if directory.is_dir():
        for path in directory.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise AudienceLedgerIntegrityError("audience snapshot cannot be decoded") from exc
            expected_sha256 = path.stem
            if canonical_sha256(payload) != expected_sha256:
                raise AudienceLedgerIntegrityError("audience snapshot hash mismatch")
            snapshot = AudienceCollectionSnapshot.model_validate(payload)
            if snapshot.platform is not platform or snapshot.account_id != account_id:
                raise AudienceLedgerIntegrityError("audience snapshot account mismatch")
            snapshots.append(snapshot)

    ordered = tuple(
        sorted(
            snapshots,
            key=lambda item: (
                item.captured_at,
                canonical_sha256(item.model_dump(mode="json")),
            ),
        )
    )
    derived_metrics: list[AudienceMetricObservation] = []
    for previous, current in zip(ordered, ordered[1:]):
        if previous.captured_at == current.captured_at:
            continue
        derived_metrics.extend(derive_longitudinal_audience_metrics(previous=previous, current=current))
    return AudienceHistory(
        platform=platform,
        account_id=account_id,
        snapshots=ordered,
        derived_metrics=tuple(derived_metrics),
    )


__all__ = [
    "AudienceHistory",
    "AudienceLedgerAppendResult",
    "AudienceLedgerIntegrityError",
    "append_audience_snapshot",
    "load_audience_history",
]
