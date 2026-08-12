from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from experiments.e15_account_evidence.frame_sampling import (
    sample_local_frames,
    sampling_timestamps,
)


def test_sampling_timestamps_cover_opening_middle_and_end_without_sampling_the_end_boundary() -> None:
    timestamps = sampling_timestamps(8.0, max_frames=6)

    assert timestamps == pytest.approx((0.1, 1.66, 3.22, 4.78, 6.34, 7.9))
    assert timestamps == tuple(sorted(timestamps))
    assert all(0 < timestamp < 8 for timestamp in timestamps)


def test_sampling_timestamps_scale_down_for_very_short_video() -> None:
    timestamps = sampling_timestamps(0.5, max_frames=6)

    assert timestamps == pytest.approx((0.025, 0.475))


def test_frame_sampler_creates_hashed_timestamped_evidence(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video-source")
    output = tmp_path / "frames"
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        Path(command[-1]).write_bytes(f"jpeg-{len(calls)}".encode())
        return subprocess.CompletedProcess(command, 0, "", "")

    frames = sample_local_frames(
        source=source,
        post_id="post-1",
        duration_seconds=3,
        output_dir=output,
        max_frames=3,
        runner=run,
    )

    assert len(frames) == 3
    assert [frame.evidence.evidence_id for frame in frames] == [
        "post-1-frame-001",
        "post-1-frame-002",
        "post-1-frame-003",
    ]
    assert all(frame.path.is_file() for frame in frames)
    assert all(frame.evidence.modality == "video_frame" for frame in frames)
    assert all(frame.evidence.artifact_ref.startswith("artifact://e15/post-1/frames/") for frame in frames)
    assert all(len(frame.evidence.content_sha256) == 64 for frame in frames)
    assert calls[0][0:3] == ["ffmpeg", "-v", "error"]
    assert "-frames:v" in calls[0]


def test_frame_sampler_cleans_partial_outputs_after_failure(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video-source")
    output = tmp_path / "frames"
    call_count = 0

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        Path(command[-1]).write_bytes(b"partial")
        return subprocess.CompletedProcess(command, 1 if call_count == 2 else 0, "", "provider secret")

    with pytest.raises(RuntimeError, match="frame extraction failed"):
        sample_local_frames(
            source=source,
            post_id="post-1",
            duration_seconds=3,
            output_dir=output,
            max_frames=3,
            runner=run,
        )

    assert not output.exists()
