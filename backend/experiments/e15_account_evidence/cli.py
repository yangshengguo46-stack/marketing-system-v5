from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from deerflow.models.factory import create_chat_model

from .contracts import SourceRights
from .mediakit import CloudCapability
from .pipeline import AccountExtractionRequest, VideoInput, run_account_extraction


def _video(value: str) -> VideoInput:
    post_id, separator, source = value.partition("=")
    if not separator or not post_id.strip() or not source.strip():
        raise argparse.ArgumentTypeError("--video must be POST_ID=/absolute/or/relative/video.mp4")
    return VideoInput(post_id=post_id.strip(), source=Path(source.strip()))


def _capability(value: str) -> CloudCapability:
    try:
        return CloudCapability(value)
    except ValueError as exc:
        choices = ", ".join(capability.value for capability in CloudCapability)
        raise argparse.ArgumentTypeError(f"cloud capability must be one of: {choices}") from exc


def _source_rights(value: str) -> SourceRights:
    try:
        return SourceRights(value)
    except ValueError as exc:
        choices = ", ".join(right.value for right in SourceRights)
        raise argparse.ArgumentTypeError(f"source rights must be one of: {choices}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the isolated E15 account-video evidence experiment.",
    )
    parser.add_argument("--account-ref", required=True)
    parser.add_argument("--video", type=_video, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="doubao-seed-evolving")
    parser.add_argument("--source-rights", type=_source_rights, required=True)
    parser.add_argument("--rights-ref", required=True)
    parser.add_argument("--max-frames", type=int, default=12)
    parser.add_argument(
        "--cloud-capability",
        type=_capability,
        action="append",
        default=[],
    )
    parser.add_argument(
        "--allow-cloud-processing",
        action="store_true",
        help="Required when any MediaKit cloud capability is requested.",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict[str, object]:
    model = create_chat_model(
        args.model,
        thinking_enabled=False,
        attach_tracing=False,
        model_overrides={"temperature": 0, "max_tokens": 4096},
    )
    request = AccountExtractionRequest(
        account_ref=args.account_ref,
        videos=tuple(args.video),
        output_dir=args.output_dir,
        model_name=args.model,
        source_rights=args.source_rights,
        rights_ref=args.rights_ref,
        captured_at=datetime.now(UTC),
        cloud_capabilities=tuple(args.cloud_capability),
        allow_cloud_processing=args.allow_cloud_processing,
        max_frames=args.max_frames,
    )
    result = await run_account_extraction(request, model=model)
    return {
        "status": "completed",
        "output_dir": str(result.output_dir),
        "video_count": len(result.pack.videos),
        "signal_count": sum(len(video.signals) for video in result.pack.videos),
        "aggregate_count": len(result.pack.aggregates),
        "limitations": list(result.pack.limitations),
    }


def main() -> int:
    args = build_parser().parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
