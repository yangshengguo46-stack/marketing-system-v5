from __future__ import annotations

import hashlib
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .contracts import EvidenceRef

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class SampledFrame:
    path: Path
    timestamp_seconds: float
    evidence: EvidenceRef


def sampling_timestamps(duration_seconds: float, *, max_frames: int = 12) -> tuple[float, ...]:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if max_frames <= 0:
        raise ValueError("max_frames must be positive")

    frame_count = min(max_frames, max(1, int(duration_seconds * 4)))
    edge_offset = min(0.1, duration_seconds * 0.05)
    if frame_count == 1:
        return (round(duration_seconds / 2, 3),)
    usable_span = duration_seconds - (2 * edge_offset)
    step = usable_span / (frame_count - 1)
    return tuple(round(edge_offset + (step * index), 3) for index in range(frame_count))


def _default_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, **kwargs)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sample_local_frames(
    *,
    source: Path,
    post_id: str,
    duration_seconds: float,
    output_dir: Path,
    max_frames: int = 12,
    runner: Runner = _default_runner,
) -> tuple[SampledFrame, ...]:
    resolved = source.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError("frame source must be an existing regular file")
    if output_dir.exists():
        raise ValueError("frame output directory must not already exist")

    output_dir.mkdir(parents=True)
    frames: list[SampledFrame] = []
    try:
        for index, timestamp in enumerate(
            sampling_timestamps(duration_seconds, max_frames=max_frames),
            start=1,
        ):
            filename = f"frame-{index:03d}-{timestamp:.3f}s.jpg"
            destination = output_dir / filename
            command = [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(resolved),
                "-frames:v",
                "1",
                "-vf",
                "scale='min(1024,iw)':-2",
                "-q:v",
                "2",
                "-y",
                str(destination),
            ]
            result = runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0 or not destination.is_file():
                raise RuntimeError("frame extraction failed")
            evidence_id = f"{post_id}-frame-{index:03d}"
            frames.append(
                SampledFrame(
                    path=destination,
                    timestamp_seconds=timestamp,
                    evidence=EvidenceRef(
                        evidence_id=evidence_id,
                        post_id=post_id,
                        modality="video_frame",
                        start_seconds=timestamp,
                        end_seconds=timestamp,
                        summary=f"从源视频 {timestamp:.3f} 秒抽取的可见帧。",
                        artifact_ref=f"artifact://e15/{post_id}/frames/{filename}",
                        content_sha256=_sha256_file(destination),
                    ),
                )
            )
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
    return tuple(frames)


__all__ = ["SampledFrame", "sample_local_frames", "sampling_timestamps"]
