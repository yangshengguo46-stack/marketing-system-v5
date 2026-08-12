from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from experiments.e15_account_evidence.mediakit import (
    CloudCapability,
    MediaKitCommandError,
    discover_capability_schema,
    discover_cli_version,
    probe_local_metadata,
    run_cloud_capability,
)


def _completed(payload: dict, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["mediakit-cli"],
        returncode=returncode,
        stdout=json.dumps(payload),
        stderr=stderr,
    )


def test_schema_is_discovered_dynamically_and_hashed() -> None:
    schema = {
        "_notice": {"skills": {"message": "not part of the capability contract"}},
        "name": "probe_video_metadata",
        "input_schema": {"type": "object", "properties": {"video_url": {"type": "string"}}},
        "output_schema": {"type": "object"},
    }
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return _completed(schema)

    result = discover_capability_schema("video", "probe-video-metadata", runner=run)

    assert calls == [["mediakit-cli", "video", "probe-video-metadata", "--schema"]]
    semantic_schema = {key: value for key, value in schema.items() if key != "_notice"}
    assert result.schema == semantic_schema
    assert result.schema_sha256 == hashlib.sha256(json.dumps(semantic_schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_cli_version_is_discovered_instead_of_hard_coded() -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "mediakit-cli version 0.2.0\n", "")

    assert discover_cli_version(runner=run) == "0.2.0"
    assert calls == [["mediakit-cli", "--version"]]


def test_cli_version_failure_is_redacted() -> None:
    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "Authorization sk-secret")

    with pytest.raises(MediaKitCommandError, match="version discovery failed") as caught:
        discover_cli_version(runner=run)

    assert "sk-secret" not in str(caught.value)


def test_local_probe_accepts_a_local_path_and_returns_a_receipt(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake-video-for-contract-test")
    schema = {
        "name": "probe_video_metadata",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }
    metadata = {
        "_notice": {"skills": {"message": "operational notice"}},
        "format_meta": {"duration": 8, "size": source.stat().st_size},
        "video_stream_meta": {"width": 1280, "height": 720, "fps": 24},
        "audio_stream_meta": {"codec": "aac"},
    }
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[-1] == "--schema":
            return _completed(schema)
        return _completed(metadata)

    result = probe_local_metadata(source, runner=run, cli_version="0.2.0")

    assert calls[1][:4] == ["mediakit-cli", "--local", "video", "probe-video-metadata"]
    assert calls[1][4:] == ["--video-url", str(source)]
    assert result.metadata == {key: value for key, value in metadata.items() if key != "_notice"}
    assert result.receipt.execution_mode == "local"
    assert result.receipt.tool_version == "0.2.0"
    assert result.receipt.input_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(result.receipt.output_sha256) == 64


def test_mediakit_errors_do_not_echo_secrets_or_provider_output(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    schema = {
        "name": "probe_video_metadata",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }
    call = 0

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        nonlocal call
        call += 1
        if call == 1:
            return _completed(schema)
        return _completed(
            {},
            returncode=1,
            stderr="Authorization: Bearer test-secret-value task_id=provider-task-123",
        )

    with pytest.raises(MediaKitCommandError) as caught:
        probe_local_metadata(source, runner=run, cli_version="0.2.0")

    message = str(caught.value)
    assert message == "MediaKit probe-video-metadata failed"
    assert "secret" not in message
    assert "provider-task" not in message


def test_local_probe_rejects_missing_or_non_file_sources(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="existing regular file"):
        probe_local_metadata(tmp_path / "missing.mp4", runner=lambda *_args, **_kwargs: _completed({}))


def test_cloud_asr_normalizes_timestamped_evidence_and_hashes_task_id(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    output = tmp_path / "cloud"
    schema = {
        "name": "asr_subtitles",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }
    responses = iter(
        [
            _completed(schema),
            _completed({"task_id": "provider-task-123", "request_id": "request-secret"}),
            _completed(
                {
                    "task_id": "provider-task-123",
                    "request_id": "request-secret",
                    "status": "completed",
                    "duration": 8,
                    "subtitles": [
                        {
                            "start_time": 0.1,
                            "end_time": 1.8,
                            "subtitle_text": "hello world",
                            "speaker": "1",
                            "confidence": 0.91,
                        }
                    ],
                }
            ),
        ]
    )
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return next(responses)

    result = run_cloud_capability(
        source=source,
        post_id="post-1",
        capability=CloudCapability.ASR,
        client_token="stable-token",
        output_dir=output,
        runner=run,
        cli_version="0.2.0",
    )

    assert result.evidence[0].modality == "asr"
    assert result.evidence[0].start_seconds == 0.1
    assert result.evidence[0].end_seconds == 1.8
    assert "hello world" in result.evidence[0].summary
    assert result.receipt.task_id_sha256 == hashlib.sha256(b"provider-task-123").hexdigest()
    serialized = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert "provider-task-123" not in serialized
    assert "request-secret" not in serialized
    assert calls[1][:4] == ["mediakit-cli", "--cloud", "video", "asr-subtitles"]
    assert calls[2][:4] == ["mediakit-cli", "shared", "query-task", "--task-id"]


def test_cloud_ocr_and_scene_results_drop_provider_urls(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    cases = (
        (
            CloudCapability.OCR,
            {
                "duration": 8,
                "subtitles": [
                    {
                        "start_time": 3.0,
                        "end_time": 3.2,
                        "subtitle_text": "5",
                        "text_label": "Others",
                        "text_location": {"top_left_x": 0, "top_left_y": 106},
                    }
                ],
            },
            "ocr",
        ),
        (
            CloudCapability.SCENE_SEGMENTATION,
            {
                "duration": 8,
                "segments": [
                    {
                        "start_time": 0,
                        "end_time": 8,
                        "segment_video_url": "https://provider.example/signed?token=secret",
                    }
                ],
            },
            "scene_segment",
        ),
    )

    for capability, semantic_result, modality in cases:
        responses = iter(
            [
                _completed({"name": capability.value, "input_schema": {}, "output_schema": {}}),
                _completed({"task_id": f"task-{capability.value}"}),
                _completed({"task_id": f"task-{capability.value}", "status": "completed", **semantic_result}),
            ]
        )
        result = run_cloud_capability(
            source=source,
            post_id="post-1",
            capability=capability,
            client_token=f"token-{capability.value}",
            output_dir=tmp_path / capability.value,
            runner=lambda *_args, **_kwargs: next(responses),
            cli_version="0.2.0",
        )
        serialized = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

        assert result.evidence[0].modality == modality
        assert "provider.example" not in serialized
        assert "token=secret" not in serialized
        assert any("machine observation" in limitation for limitation in result.limitations)


def test_cloud_failure_is_redacted_and_does_not_leave_raw_result(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    responses = iter(
        [
            _completed({"name": "asr_subtitles", "input_schema": {}, "output_schema": {}}),
            _completed({"task_id": "task-secret"}),
            _completed(
                {
                    "task_id": "task-secret",
                    "status": "failed",
                    "error": "Authorization Bearer sk-secret signed=https://provider.example/x",
                }
            ),
        ]
    )

    with pytest.raises(MediaKitCommandError) as caught:
        run_cloud_capability(
            source=source,
            post_id="post-1",
            capability=CloudCapability.ASR,
            client_token="stable-token",
            output_dir=tmp_path / "cloud",
            runner=lambda *_args, **_kwargs: next(responses),
            cli_version="0.2.0",
        )

    assert str(caught.value) == "MediaKit asr cloud task failed"
    assert not (tmp_path / "cloud" / "raw-provider-result.json").exists()
