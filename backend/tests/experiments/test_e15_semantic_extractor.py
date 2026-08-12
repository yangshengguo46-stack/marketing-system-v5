from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from experiments.e15_account_evidence.contracts import (
    MediaObservation,
    SignalDimension,
    SourceRights,
)
from experiments.e15_account_evidence.frame_sampling import sample_local_frames
from experiments.e15_account_evidence.semantic_extractor import (
    EXTRACTOR_SYSTEM_PROMPT,
    SemanticExtractorError,
    extract_semantic_signals,
)

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def _frames(tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video-source")

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        Path(command[-1]).write_bytes(b"jpeg" + command[-1].encode())
        return subprocess.CompletedProcess(command, 0, "", "")

    return source, sample_local_frames(
        source=source,
        post_id="post-1",
        duration_seconds=3,
        output_dir=tmp_path / "frames",
        max_frames=3,
        runner=run,
    )


class FakeModel:
    def __init__(self, response: AIMessage) -> None:
        self.response = response
        self.messages = None
        self.kwargs = None

    async def ainvoke(self, messages, **kwargs):
        self.messages = messages
        self.kwargs = kwargs
        return self.response


def _valid_payload() -> dict:
    return {
        "signals": [
            {
                "signal_id": "post-1-presentation-format-cinematic-scene",
                "post_id": "post-1",
                "dimension": "presentation_format",
                "label": "cinematic-scene",
                "statement": "画面通过两名角色的电影化情境表演承载内容。",
                "epistemic_status": "observed",
                "evidence_refs": ["post-1-frame-001", "post-1-frame-002"],
                "confidence": 0.86,
                "alternative_explanations": [],
                "unknown_question": None,
            },
            {
                "signal_id": "post-1-opening-function-tension",
                "post_id": "post-1",
                "dimension": "opening_function",
                "label": "relationship-tension",
                "statement": "开场似乎用人物关系紧张感建立观看问题。",
                "epistemic_status": "inferred",
                "evidence_refs": ["post-1-frame-001"],
                "confidence": 0.61,
                "alternative_explanations": ["静帧无法确认开场前后信息顺序。"],
                "unknown_question": None,
            },
        ]
    }


@pytest.mark.asyncio
async def test_extractor_only_exposes_supplied_frames_and_returns_valid_record(tmp_path: Path) -> None:
    source, frames = _frames(tmp_path)
    media = MediaObservation(
        post_id="post-1",
        source_sha256="a" * 64,
        duration_seconds=3,
        evidence=tuple(frame.evidence for frame in frames),
        limitations=("ASR 未取得。",),
    )
    model = FakeModel(
        AIMessage(
            content=json.dumps(_valid_payload(), ensure_ascii=False),
            additional_kwargs={"reasoning_content": "hidden provider reasoning must disappear"},
            response_metadata={"model_name": "fixture-vision-model"},
        )
    )

    record = await extract_semantic_signals(
        model=model,
        model_name="fixture-vision-model",
        account_ref="account://demo/one",
        post_id="post-1",
        source_rights=SourceRights.USER_OWNED,
        rights_ref="rights://demo/user-owned",
        captured_at=NOW,
        source=source,
        media=media,
        frames=frames,
    )

    assert {signal.dimension for signal in record.signals} == {
        SignalDimension.PRESENTATION_FORMAT,
        SignalDimension.OPENING_FUNCTION,
    }
    assert record.extractor_receipt.model_name == "fixture-vision-model"
    assert not hasattr(record.extractor_receipt, "reasoning_content")
    encoded = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
    assert "hidden provider reasoning" not in encoded

    human_blocks = model.messages[1].content
    image_blocks = [block for block in human_blocks if block["type"] == "image_url"]
    text = "\n".join(block["text"] for block in human_blocks if block["type"] == "text")
    assert len(image_blocks) == 3
    assert all(block["image_url"]["url"].startswith("data:image/jpeg;base64,") for block in image_blocks)
    assert "post-1-frame-001" in text
    assert str(source) not in text
    assert model.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_extractor_includes_non_visual_media_atoms_without_exposing_source_path(tmp_path: Path) -> None:
    source, frames = _frames(tmp_path)
    asr_evidence = frames[0].evidence.model_copy(
        update={
            "evidence_id": "post-1-asr-001",
            "modality": "asr",
            "start_seconds": 0.1,
            "end_seconds": 1.8,
            "summary": "ASR machine observation: hello world",
            "artifact_ref": "artifact://e15/post-1/mediakit/asr/001",
        }
    )
    media = MediaObservation(
        post_id="post-1",
        source_sha256="a" * 64,
        duration_seconds=3,
        evidence=tuple(frame.evidence for frame in frames) + (asr_evidence,),
        limitations=("ASR is a machine observation and may be wrong.",),
    )
    model = FakeModel(AIMessage(content=json.dumps(_valid_payload())))

    await extract_semantic_signals(
        model=model,
        model_name="fixture-model",
        account_ref="account://demo/one",
        post_id="post-1",
        source_rights=SourceRights.USER_OWNED,
        rights_ref="rights://demo/user-owned",
        captured_at=NOW,
        source=source,
        media=media,
        frames=frames,
    )

    text = "\n".join(block["text"] for block in model.messages[1].content if block["type"] == "text")
    assert "post-1-asr-001" in text
    assert "hello world" in text
    assert str(source) not in text


@pytest.mark.asyncio
async def test_extractor_rejects_markdown_wrapped_json(tmp_path: Path) -> None:
    source, frames = _frames(tmp_path)
    media = MediaObservation(
        post_id="post-1",
        source_sha256="a" * 64,
        duration_seconds=3,
        evidence=tuple(frame.evidence for frame in frames),
    )
    model = FakeModel(AIMessage(content=f"```json\n{json.dumps(_valid_payload())}\n```"))

    with pytest.raises(SemanticExtractorError, match="direct JSON object"):
        await extract_semantic_signals(
            model=model,
            model_name="fixture-model",
            account_ref="account://demo/one",
            post_id="post-1",
            source_rights=SourceRights.USER_OWNED,
            rights_ref="rights://demo/user-owned",
            captured_at=NOW,
            source=source,
            media=media,
            frames=frames,
        )


@pytest.mark.asyncio
async def test_extractor_rejects_signal_that_cites_an_unseen_frame(tmp_path: Path) -> None:
    source, frames = _frames(tmp_path)
    media = MediaObservation(
        post_id="post-1",
        source_sha256="a" * 64,
        duration_seconds=3,
        evidence=tuple(frame.evidence for frame in frames),
    )
    payload = _valid_payload()
    payload["signals"][0]["evidence_refs"] = ["post-1-frame-999"]
    model = FakeModel(AIMessage(content=json.dumps(payload)))

    with pytest.raises(SemanticExtractorError, match="schema or evidence validation"):
        await extract_semantic_signals(
            model=model,
            model_name="fixture-model",
            account_ref="account://demo/one",
            post_id="post-1",
            source_rights=SourceRights.USER_OWNED,
            rights_ref="rights://demo/user-owned",
            captured_at=NOW,
            source=source,
            media=media,
            frames=frames,
        )


def test_extractor_prompt_has_no_quota_or_account_decision_authority() -> None:
    lowered = EXTRACTOR_SYSTEM_PROMPT.lower()

    assert "固定数量" not in EXTRACTOR_SYSTEM_PROMPT
    assert "至少三" not in EXTRACTOR_SYSTEM_PROMPT
    assert "账号定位结论" in EXTRACTOR_SYSTEM_PROMPT
    assert "时代" in EXTRACTOR_SYSTEM_PROMPT
    assert "人物身份" in EXTRACTOR_SYSTEM_PROMPT
    assert "不属于直接观察" in EXTRACTOR_SYSTEM_PROMPT
    assert "不得" in EXTRACTOR_SYSTEM_PROMPT
    assert "account verdict" not in lowered
