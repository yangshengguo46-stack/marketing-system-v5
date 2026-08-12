from __future__ import annotations

import inspect
import json
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .aggregation import aggregate_account_records
from .contracts import (
    AccountEvidencePack,
    MediaObservation,
    SourceRights,
    canonical_sha256,
)
from .frame_sampling import SampledFrame, sample_local_frames
from .mediakit import (
    CloudCapability,
    CloudCapabilityResult,
    MetadataProbeResult,
    probe_local_metadata,
    run_cloud_capability,
)
from .review import build_evidence_review_queue, build_signal_review_queue
from .semantic_extractor import extract_semantic_signals

CONTRACT_VERSION = "e15-account-evidence-run-v1"


class VideoInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)
    post_id: str = Field(min_length=1, max_length=160)
    source: Path

    @field_validator("source")
    @classmethod
    def existing_source(cls, value: Path) -> Path:
        resolved = value.expanduser().resolve()
        if not resolved.is_file():
            raise ValueError("video source must be an existing regular file")
        return resolved


class AccountExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)
    account_ref: str = Field(min_length=1, max_length=500)
    videos: tuple[VideoInput, ...] = Field(min_length=1)
    output_dir: Path
    model_name: str = Field(min_length=1, max_length=160)
    source_rights: SourceRights
    rights_ref: str = Field(min_length=1, max_length=1_000)
    captured_at: datetime
    cloud_capabilities: tuple[CloudCapability, ...] = Field(default_factory=tuple)
    allow_cloud_processing: bool = False
    max_frames: int = Field(default=12, ge=1, le=24)

    @model_validator(mode="after")
    def validate_request(self) -> AccountExtractionRequest:
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        post_ids = [video.post_id for video in self.videos]
        if len(set(post_ids)) != len(post_ids):
            raise ValueError("video post ids must be unique")
        output = self.output_dir.expanduser().resolve()
        if output.exists():
            raise ValueError("output_dir must not exist")
        object.__setattr__(self, "output_dir", output)
        if self.cloud_capabilities and not self.allow_cloud_processing:
            raise ValueError("cloud capabilities require allow_cloud_processing=true")
        if len(set(self.cloud_capabilities)) != len(self.cloud_capabilities):
            raise ValueError("cloud capabilities must be unique")
        return self


@dataclass(frozen=True, slots=True)
class AccountExtractionResult:
    pack: AccountEvidencePack
    output_dir: Path


def _duration(metadata: dict[str, Any]) -> float:
    format_meta = metadata.get("format_meta")
    duration = format_meta.get("duration") if isinstance(format_meta, dict) else None
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
        raise ValueError("MediaKit metadata does not contain a positive duration")
    return float(duration)


def _cloud_client_token(
    *,
    account_ref: str,
    post_id: str,
    capability: CloudCapability,
    source_sha256: str,
) -> str:
    digest = canonical_sha256(
        {
            "account": account_ref,
            "post": post_id,
            "capability": capability.value,
            "source_sha256": source_sha256,
        }
    )
    return f"e15-{digest[:40]}"


def _atomic_write_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _invoke(function: Callable[..., Any], **kwargs: Any) -> Any:
    parameters = inspect.signature(function).parameters
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return function(**kwargs)
    accepted = {key: value for key, value in kwargs.items() if key in parameters}
    return function(**accepted)


async def run_account_extraction(
    request: AccountExtractionRequest,
    *,
    model: Any,
    metadata_probe: Callable[..., MetadataProbeResult] = probe_local_metadata,
    frame_sampler: Callable[..., tuple[SampledFrame, ...]] = sample_local_frames,
    cloud_runner: Callable[..., CloudCapabilityResult] = run_cloud_capability,
) -> AccountExtractionResult:
    output = request.output_dir
    staging = output.with_name(f".{output.name}.staging-{uuid.uuid4().hex}")
    if staging.exists():
        raise ValueError("staging output already exists")
    staging.mkdir(parents=True)
    records = []
    account_limitations: list[str] = []
    try:
        for video in request.videos:
            video_dir = staging / "videos" / video.post_id
            probe: MetadataProbeResult = _invoke(metadata_probe, source=video.source)
            duration_seconds = _duration(probe.metadata)
            frames: tuple[SampledFrame, ...] = _invoke(
                frame_sampler,
                source=video.source,
                post_id=video.post_id,
                duration_seconds=duration_seconds,
                output_dir=video_dir / "frames",
                max_frames=request.max_frames,
            )

            evidence = list(frame.evidence for frame in frames)
            receipts = [probe.receipt]
            limitations: list[str] = []
            for capability in request.cloud_capabilities:
                try:
                    cloud: CloudCapabilityResult = _invoke(
                        cloud_runner,
                        source=video.source,
                        post_id=video.post_id,
                        capability=capability,
                        client_token=_cloud_client_token(
                            account_ref=request.account_ref,
                            post_id=video.post_id,
                            capability=capability,
                            source_sha256=probe.receipt.input_sha256,
                        ),
                        output_dir=video_dir / "mediakit" / capability.value,
                    )
                except Exception:
                    limitation = f"MediaKit {capability.value} unavailable for {video.post_id}."
                    limitations.append(limitation)
                    account_limitations.append(limitation)
                    continue
                evidence.extend(cloud.evidence)
                receipts.append(cloud.receipt)
                limitations.extend(cloud.limitations)

            media = MediaObservation(
                post_id=video.post_id,
                source_sha256=probe.receipt.input_sha256,
                duration_seconds=duration_seconds,
                evidence=tuple(evidence),
                receipts=tuple(receipts),
                limitations=tuple(limitations),
            )
            record = await extract_semantic_signals(
                model=model,
                model_name=request.model_name,
                account_ref=request.account_ref,
                post_id=video.post_id,
                source_rights=request.source_rights,
                rights_ref=request.rights_ref,
                captured_at=request.captured_at,
                source=video.source,
                media=media,
                frames=frames,
            )
            records.append(record)

        pack = aggregate_account_records(
            tuple(records),
            generated_at=request.captured_at,
        )
        pack = pack.model_copy(update={"limitations": tuple(dict.fromkeys((*pack.limitations, *account_limitations)))})
        pack_payload = pack.model_dump(mode="json")
        review_queue = build_signal_review_queue(pack).model_dump(mode="json")
        evidence_review_queue = build_evidence_review_queue(pack).model_dump(mode="json")
        manifest = {
            "contract_version": CONTRACT_VERSION,
            "account_ref": request.account_ref,
            "captured_at": request.captured_at.isoformat(),
            "model_name": request.model_name,
            "source_rights": request.source_rights.value,
            "rights_ref": request.rights_ref,
            "post_ids": [video.post_id for video in request.videos],
            "cloud_capabilities": [capability.value for capability in request.cloud_capabilities],
            "cloud_processing_consent": request.allow_cloud_processing,
            "pack_sha256": canonical_sha256(pack_payload),
            "review_queue_sha256": canonical_sha256(review_queue),
            "evidence_review_queue_sha256": canonical_sha256(evidence_review_queue),
        }
        _atomic_write_json(staging / "account-evidence-pack.json", pack_payload)
        _atomic_write_json(staging / "signal-review-queue.json", review_queue)
        _atomic_write_json(
            staging / "evidence-review-queue.json",
            evidence_review_queue,
        )
        _atomic_write_json(staging / "manifest.json", manifest)
        staging.replace(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return AccountExtractionResult(pack=pack, output_dir=output)


__all__ = [
    "AccountExtractionRequest",
    "AccountExtractionResult",
    "VideoInput",
    "run_account_extraction",
]
