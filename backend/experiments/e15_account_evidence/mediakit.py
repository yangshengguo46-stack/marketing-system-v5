from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from .contracts import EvidenceRef, MediaKitReceipt, StrictModel, canonical_sha256

Runner = Callable[..., subprocess.CompletedProcess[str]]


class MediaKitCommandError(RuntimeError):
    """A redacted MediaKit process or payload failure."""


@dataclass(frozen=True, slots=True)
class CapabilitySchema:
    schema: dict[str, Any]
    schema_sha256: str


@dataclass(frozen=True, slots=True)
class MetadataProbeResult:
    metadata: dict[str, Any]
    receipt: MediaKitReceipt


class CloudCapability(StrEnum):
    ASR = "asr"
    OCR = "ocr"
    SCENE_SEGMENTATION = "scene_segmentation"


class CloudCapabilityResult(StrictModel):
    capability: CloudCapability
    evidence: tuple[EvidenceRef, ...]
    receipt: MediaKitReceipt
    limitations: tuple[str, ...] = Field(default_factory=tuple)


_CLOUD_COMMANDS: dict[CloudCapability, tuple[str, tuple[str, ...]]] = {
    CloudCapability.ASR: (
        "asr-subtitles",
        ("--video-url", "{source}", "--enable-speaker-info=true", "--enable-confidence=true"),
    ),
    CloudCapability.OCR: (
        "video-ocr",
        ("--video-url", "{source}", "--mode", "Detailed"),
    ),
    CloudCapability.SCENE_SEGMENTATION: (
        "segment-scenes",
        ("--video-url", "{source}"),
    ),
}


def _default_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, **kwargs)


def _json_result(
    result: subprocess.CompletedProcess[str],
    *,
    failure_label: str,
    allow_error_payload: bool = False,
) -> dict[str, Any]:
    if result.returncode != 0:
        raise MediaKitCommandError(f"MediaKit {failure_label} failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaKitCommandError(f"MediaKit {failure_label} returned invalid JSON") from exc
    if not isinstance(payload, dict) or (payload.get("error") and not allow_error_payload):
        raise MediaKitCommandError(f"MediaKit {failure_label} returned an invalid result")
    return {key: value for key, value in payload.items() if key != "_notice"}


def discover_capability_schema(
    domain: str,
    tool: str,
    *,
    runner: Runner = _default_runner,
) -> CapabilitySchema:
    result = runner(
        ["mediakit-cli", domain, tool, "--schema"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    schema = _json_result(result, failure_label=f"{tool} schema discovery")
    return CapabilitySchema(schema=schema, schema_sha256=canonical_sha256(schema))


def discover_cli_version(*, runner: Runner = _default_runner) -> str:
    result = runner(
        ["mediakit-cli", "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise MediaKitCommandError("MediaKit version discovery failed")
    prefix = "mediakit-cli version "
    output = result.stdout.strip()
    if not output.startswith(prefix) or not output.removeprefix(prefix).strip():
        raise MediaKitCommandError("MediaKit version discovery returned an invalid result")
    return output.removeprefix(prefix).strip()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_local_metadata(
    source: Path,
    *,
    runner: Runner = _default_runner,
    cli_version: str | None = None,
) -> MetadataProbeResult:
    resolved = source.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError("MediaKit source must be an existing regular file")

    schema = discover_capability_schema("video", "probe-video-metadata", runner=runner)
    result = runner(
        [
            "mediakit-cli",
            "--local",
            "video",
            "probe-video-metadata",
            "--video-url",
            str(resolved),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    metadata = _json_result(result, failure_label="probe-video-metadata")
    input_sha256 = _file_sha256(resolved)
    return MetadataProbeResult(
        metadata=metadata,
        receipt=MediaKitReceipt(
            capability="probe-video-metadata",
            execution_mode="local",
            tool_version=cli_version or discover_cli_version(runner=runner),
            schema_sha256=schema.schema_sha256,
            input_sha256=input_sha256,
            output_sha256=canonical_sha256(metadata),
        ),
    )


def _cloud_evidence(
    *,
    post_id: str,
    capability: CloudCapability,
    payload: dict[str, Any],
) -> tuple[EvidenceRef, ...]:
    evidence: list[EvidenceRef] = []
    if capability in {CloudCapability.ASR, CloudCapability.OCR}:
        subtitles = payload.get("subtitles")
        if not isinstance(subtitles, list):
            raise MediaKitCommandError(f"MediaKit {capability.value} returned an invalid semantic result")
        modality = capability.value
        for index, item in enumerate(subtitles, start=1):
            if not isinstance(item, dict):
                raise MediaKitCommandError(f"MediaKit {capability.value} returned an invalid semantic result")
            text = str(item.get("subtitle_text") or "").strip()
            start = item.get("start_time")
            end = item.get("end_time")
            if not text or isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                raise MediaKitCommandError(f"MediaKit {capability.value} returned an invalid semantic result")
            semantic_item: dict[str, Any] = {
                "start_time": float(start),
                "end_time": float(end),
                "subtitle_text": text,
            }
            if capability is CloudCapability.ASR:
                for field_name in ("speaker", "confidence"):
                    if field_name in item:
                        semantic_item[field_name] = item[field_name]
                details = []
                if item.get("speaker") is not None:
                    details.append(f"speaker={item['speaker']}")
                if isinstance(item.get("confidence"), (int, float)) and not isinstance(item.get("confidence"), bool):
                    details.append(f"confidence={float(item['confidence']):.3f}")
                suffix = f" ({', '.join(details)})" if details else ""
                summary = f"ASR machine observation: {text}{suffix}"
            else:
                if item.get("text_label") is not None:
                    semantic_item["text_label"] = item["text_label"]
                if isinstance(item.get("text_location"), dict):
                    semantic_item["text_location"] = item["text_location"]
                summary = f"OCR machine observation: {text}"
            evidence.append(
                EvidenceRef(
                    evidence_id=f"{post_id}-{modality}-{index:03d}",
                    post_id=post_id,
                    modality=modality,
                    start_seconds=float(start),
                    end_seconds=float(end),
                    summary=summary,
                    artifact_ref=f"artifact://e15/{post_id}/mediakit/{modality}/{index:03d}",
                    content_sha256=canonical_sha256(semantic_item),
                )
            )
    else:
        segments = payload.get("segments")
        if not isinstance(segments, list):
            raise MediaKitCommandError("MediaKit scene_segmentation returned an invalid semantic result")
        for index, item in enumerate(segments, start=1):
            if not isinstance(item, dict):
                raise MediaKitCommandError("MediaKit scene_segmentation returned an invalid semantic result")
            start = item.get("start_time")
            end = item.get("end_time")
            if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                raise MediaKitCommandError("MediaKit scene_segmentation returned an invalid semantic result")
            semantic_item = {"start_time": float(start), "end_time": float(end)}
            evidence.append(
                EvidenceRef(
                    evidence_id=f"{post_id}-scene-{index:03d}",
                    post_id=post_id,
                    modality="scene_segment",
                    start_seconds=float(start),
                    end_seconds=float(end),
                    summary=f"MediaKit scene-boundary machine observation from {float(start):.3f}s to {float(end):.3f}s.",
                    artifact_ref=f"artifact://e15/{post_id}/mediakit/scene/{index:03d}",
                    content_sha256=canonical_sha256(semantic_item),
                )
            )
    return tuple(evidence)


def _semantic_cloud_payload(
    payload: dict[str, Any],
    capability: CloudCapability,
) -> dict[str, Any]:
    semantic: dict[str, Any] = {}
    duration = payload.get("duration")
    if isinstance(duration, (int, float)) and not isinstance(duration, bool):
        semantic["duration"] = float(duration)
    if capability in {CloudCapability.ASR, CloudCapability.OCR}:
        subtitles = payload.get("subtitles")
        if isinstance(subtitles, list):
            allowed = {"start_time", "end_time", "subtitle_text"}
            if capability is CloudCapability.ASR:
                allowed.update({"speaker", "confidence"})
            else:
                allowed.update({"text_label", "text_location"})
            semantic["subtitles"] = [{key: value for key, value in item.items() if key in allowed} for item in subtitles if isinstance(item, dict)]
    else:
        segments = payload.get("segments")
        if isinstance(segments, list):
            semantic["segments"] = [{key: value for key, value in item.items() if key in {"start_time", "end_time"}} for item in segments if isinstance(item, dict)]
    return semantic


def run_cloud_capability(
    *,
    source: Path,
    post_id: str,
    capability: CloudCapability,
    client_token: str,
    output_dir: Path,
    runner: Runner = _default_runner,
    cli_version: str | None = None,
) -> CloudCapabilityResult:
    resolved = source.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError("MediaKit source must be an existing regular file")
    if not client_token or len(client_token) > 64 or any(ord(character) < 33 or ord(character) > 126 for character in client_token):
        raise ValueError("MediaKit client_token must contain 1-64 visible ASCII characters")
    if not isinstance(capability, CloudCapability):
        raise ValueError("unsupported MediaKit cloud capability")

    command_name, template_args = _CLOUD_COMMANDS[capability]
    schema = discover_capability_schema("video", command_name, runner=runner)
    output_dir.mkdir(parents=True, exist_ok=True)
    arguments = [str(resolved) if value == "{source}" else value for value in template_args]
    submit = runner(
        [
            "mediakit-cli",
            "--cloud",
            "video",
            command_name,
            *arguments,
            "--client-token",
            client_token,
            "--output-path",
            str(output_dir.resolve()),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    submitted = _json_result(submit, failure_label=f"{capability.value} cloud submission")
    task_id = str(submitted.get("task_id") or "").strip()
    if not task_id:
        raise MediaKitCommandError(f"MediaKit {capability.value} cloud submission did not return task_id")

    query = runner(
        [
            "mediakit-cli",
            "shared",
            "query-task",
            "--task-id",
            task_id,
            "--poll-complete",
            "--poll-interval-seconds",
            "3",
            "--max-poll-attempts",
            "60",
            "--output-path",
            str(output_dir.resolve()),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    final = _json_result(
        query,
        failure_label=f"{capability.value} cloud query",
        allow_error_payload=True,
    )
    if str(final.get("task_id") or "").strip() != task_id:
        raise MediaKitCommandError(f"MediaKit {capability.value} cloud task identity mismatch")
    if str(final.get("status") or "").strip().lower() != "completed":
        raise MediaKitCommandError(f"MediaKit {capability.value} cloud task failed")

    semantic_payload = _semantic_cloud_payload(final, capability)
    evidence = _cloud_evidence(post_id=post_id, capability=capability, payload=semantic_payload)
    if not evidence:
        raise MediaKitCommandError(f"MediaKit {capability.value} completed without semantic evidence")
    source_sha256 = _file_sha256(resolved)
    limitation = f"MediaKit {capability.value} output is a machine observation; preserve it as evidence and review errors before treating it as fact."
    return CloudCapabilityResult(
        capability=capability,
        evidence=evidence,
        receipt=MediaKitReceipt(
            capability=command_name,
            execution_mode="cloud",
            tool_version=cli_version or discover_cli_version(runner=runner),
            schema_sha256=schema.schema_sha256,
            input_sha256=source_sha256,
            output_sha256=canonical_sha256(semantic_payload),
            task_id_sha256=hashlib.sha256(task_id.encode()).hexdigest(),
            client_token_sha256=hashlib.sha256(client_token.encode()).hexdigest(),
        ),
        limitations=(limitation,),
    )


__all__ = [
    "CapabilitySchema",
    "CloudCapability",
    "CloudCapabilityResult",
    "MediaKitCommandError",
    "MetadataProbeResult",
    "discover_capability_schema",
    "discover_cli_version",
    "probe_local_metadata",
    "run_cloud_capability",
]
