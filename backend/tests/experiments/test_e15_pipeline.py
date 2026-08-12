from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from experiments.e15_account_evidence.contracts import (
    EvidenceRef,
    MediaKitReceipt,
    SourceRights,
)
from experiments.e15_account_evidence.frame_sampling import SampledFrame
from experiments.e15_account_evidence.mediakit import (
    CloudCapability,
    CloudCapabilityResult,
    MetadataProbeResult,
)
from experiments.e15_account_evidence.pipeline import (
    AccountExtractionRequest,
    VideoInput,
    _cloud_client_token,
    run_account_extraction,
)

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


class FakeModel:
    async def ainvoke(self, messages, **_kwargs):
        text = "\n".join(block.get("text", "") for block in messages[1].content if isinstance(block, dict))
        post_id = "post-2" if "post-2-frame-001" in text else "post-1"
        return AIMessage(
            content=json.dumps(
                {
                    "signals": [
                        {
                            "signal_id": f"{post_id}-presentation-format-scene",
                            "post_id": post_id,
                            "dimension": "presentation_format",
                            "label": "situational-scene",
                            "statement": "画面通过人物情境承载内容。",
                            "epistemic_status": "observed",
                            "evidence_refs": [f"{post_id}-frame-001"],
                            "confidence": 0.8,
                            "alternative_explanations": [],
                            "unknown_question": None,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )


def _probe(source: Path, **_kwargs) -> MetadataProbeResult:
    source_hash = "a" * 64 if source.name == "one.mp4" else "b" * 64
    return MetadataProbeResult(
        metadata={
            "format_meta": {"duration": 8, "size": source.stat().st_size},
            "video_stream_meta": {"width": 1280, "height": 720, "fps": 24},
        },
        receipt=MediaKitReceipt(
            capability="probe-video-metadata",
            execution_mode="local",
            tool_version="0.2.0",
            schema_sha256="c" * 64,
            input_sha256=source_hash,
            output_sha256="d" * 64,
        ),
    )


def _frames(*, source: Path, post_id: str, output_dir: Path, **_kwargs):
    output_dir.mkdir(parents=True)
    path = output_dir / "frame-001.jpg"
    path.write_bytes(b"jpeg")
    return (
        SampledFrame(
            path=path,
            timestamp_seconds=1,
            evidence=EvidenceRef(
                evidence_id=f"{post_id}-frame-001",
                post_id=post_id,
                modality="video_frame",
                start_seconds=1,
                end_seconds=1,
                summary="一张测试帧。",
                artifact_ref=f"artifact://e15/{post_id}/frames/frame-001.jpg",
                content_sha256="e" * 64,
            ),
        ),
    )


def _cloud(*, post_id: str, capability: CloudCapability, **_kwargs) -> CloudCapabilityResult:
    modality = "asr" if capability is CloudCapability.ASR else capability.value
    return CloudCapabilityResult(
        capability=capability,
        evidence=(
            EvidenceRef(
                evidence_id=f"{post_id}-{modality}-001",
                post_id=post_id,
                modality=modality,
                start_seconds=0,
                end_seconds=2,
                summary=f"{capability.value} machine observation",
                artifact_ref=f"artifact://e15/{post_id}/mediakit/{modality}/001",
                content_sha256="f" * 64,
            ),
        ),
        receipt=MediaKitReceipt(
            capability=capability.value,
            execution_mode="cloud",
            tool_version="0.2.0",
            schema_sha256="1" * 64,
            input_sha256="a" * 64 if post_id == "post-1" else "b" * 64,
            output_sha256="2" * 64,
            task_id_sha256="3" * 64,
            client_token_sha256="4" * 64,
        ),
        limitations=(f"{capability.value} is a machine observation.",),
    )


@pytest.mark.asyncio
async def test_pipeline_builds_multi_video_pack_manifest_and_review_queue(tmp_path: Path) -> None:
    first = tmp_path / "one.mp4"
    second = tmp_path / "two.mp4"
    first.write_bytes(b"video-one")
    second.write_bytes(b"video-two")
    output = tmp_path / "result"
    request = AccountExtractionRequest(
        account_ref="account://demo/one",
        videos=(VideoInput(post_id="post-1", source=first), VideoInput(post_id="post-2", source=second)),
        output_dir=output,
        model_name="fixture-model",
        source_rights=SourceRights.USER_OWNED,
        rights_ref="rights://fixture/user-owned",
        captured_at=NOW,
        cloud_capabilities=(CloudCapability.ASR,),
        allow_cloud_processing=True,
        max_frames=3,
    )

    result = await run_account_extraction(
        request,
        model=FakeModel(),
        metadata_probe=_probe,
        frame_sampler=_frames,
        cloud_runner=_cloud,
    )

    assert output.is_dir()
    assert result.pack.account_ref == "account://demo/one"
    assert len(result.pack.videos) == 2
    repeated = result.pack.aggregates[0]
    assert repeated.label == "situational-scene"
    assert repeated.supporting_post_ids == ("post-1", "post-2")
    assert repeated.support_status == "repeated_support"
    assert "asr is a machine observation." in result.pack.limitations

    pack_json = json.loads((output / "account-evidence-pack.json").read_text())
    manifest = json.loads((output / "manifest.json").read_text())
    review = json.loads((output / "signal-review-queue.json").read_text())
    evidence_review = json.loads((output / "evidence-review-queue.json").read_text())
    serialized = json.dumps(
        {
            "pack": pack_json,
            "manifest": manifest,
            "review": review,
            "evidence_review": evidence_review,
        }
    )
    assert manifest["contract_version"] == "e15-account-evidence-run-v1"
    assert manifest["source_rights"] == "user_owned"
    assert manifest["rights_ref"] == "rights://fixture/user-owned"
    assert len(manifest["pack_sha256"]) == 64
    assert len(manifest["evidence_review_queue_sha256"]) == 64
    assert "asr is a machine observation." in pack_json["limitations"]
    assert {item["disposition"] for item in review["items"]} == {"pending"}
    assert {item["modality"] for item in evidence_review["items"]} == {"asr"}
    assert str(first) not in serialized
    assert str(second) not in serialized
    assert "reasoning_content" not in serialized


def test_request_requires_explicit_consent_for_cloud_processing(tmp_path: Path) -> None:
    source = tmp_path / "one.mp4"
    source.write_bytes(b"video")

    with pytest.raises(ValueError, match="allow_cloud_processing"):
        AccountExtractionRequest(
            account_ref="account://demo/one",
            videos=(VideoInput(post_id="post-1", source=source),),
            output_dir=tmp_path / "result",
            model_name="fixture-model",
            source_rights=SourceRights.USER_OWNED,
            rights_ref="rights://fixture/user-owned",
            captured_at=NOW,
            cloud_capabilities=(CloudCapability.ASR,),
            allow_cloud_processing=False,
        )


def test_request_rejects_duplicate_posts_and_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "one.mp4"
    source.write_bytes(b"video")
    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(ValueError, match="post ids must be unique"):
        AccountExtractionRequest(
            account_ref="account://demo/one",
            videos=(VideoInput(post_id="post-1", source=source), VideoInput(post_id="post-1", source=source)),
            output_dir=tmp_path / "new",
            model_name="fixture-model",
            source_rights=SourceRights.USER_OWNED,
            rights_ref="rights://fixture/user-owned",
            captured_at=NOW,
        )

    with pytest.raises(ValueError, match="output_dir must not exist"):
        AccountExtractionRequest(
            account_ref="account://demo/one",
            videos=(VideoInput(post_id="post-1", source=source),),
            output_dir=existing,
            model_name="fixture-model",
            source_rights=SourceRights.USER_OWNED,
            rights_ref="rights://fixture/user-owned",
            captured_at=NOW,
        )


@pytest.mark.asyncio
async def test_cloud_failure_becomes_a_limitation_instead_of_losing_local_evidence(tmp_path: Path) -> None:
    source = tmp_path / "one.mp4"
    source.write_bytes(b"video")
    request = AccountExtractionRequest(
        account_ref="account://demo/one",
        videos=(VideoInput(post_id="post-1", source=source),),
        output_dir=tmp_path / "result",
        model_name="fixture-model",
        source_rights=SourceRights.ANALYSIS_ONLY,
        rights_ref="rights://fixture/analysis-only",
        captured_at=NOW,
        cloud_capabilities=(CloudCapability.ASR,),
        allow_cloud_processing=True,
    )

    def fail_cloud(**_kwargs):
        raise RuntimeError("Authorization sk-secret provider-url")

    result = await run_account_extraction(
        request,
        model=FakeModel(),
        metadata_probe=_probe,
        frame_sampler=_frames,
        cloud_runner=fail_cloud,
    )

    assert result.pack.videos[0].media.evidence[0].modality == "video_frame"
    assert "MediaKit asr unavailable for post-1." in result.pack.limitations
    encoded = json.dumps(result.pack.model_dump(mode="json"))
    assert "sk-secret" not in encoded
    assert "provider-url" not in encoded


def test_cloud_client_token_is_stable_for_same_input_and_changes_with_source() -> None:
    first = _cloud_client_token(
        account_ref="account://demo/one",
        post_id="post-1",
        capability=CloudCapability.ASR,
        source_sha256="a" * 64,
    )
    repeated = _cloud_client_token(
        account_ref="account://demo/one",
        post_id="post-1",
        capability=CloudCapability.ASR,
        source_sha256="a" * 64,
    )
    changed_source = _cloud_client_token(
        account_ref="account://demo/one",
        post_id="post-1",
        capability=CloudCapability.ASR,
        source_sha256="b" * 64,
    )

    assert first == repeated
    assert first != changed_source
    assert first.startswith("e15-")
    assert len(first) <= 64
