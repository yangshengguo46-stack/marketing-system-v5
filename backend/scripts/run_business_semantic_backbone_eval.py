"""Evaluate the production business-semantic contract in offline isolation.

The evaluator and the runtime tool share one prompt and parser. This script
still does not call the Lead or register tools; it only exercises the bounded
semantic contract against sealed cases.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from deerflow.config.app_config import get_app_config
from deerflow.models.factory import create_chat_model
from deerflow.tools.builtins.business_semantics_tool import (
    BUSINESS_SEMANTIC_BACKBONE_SYSTEM_PROMPT,
    build_semantic_messages,
    parse_business_semantics,
)
from scripts.run_marketing_brain_eval import (
    AsyncModel,
    BrainEvalCase,
    default_cases,
    extract_provider_reasoning,
    extract_visible_answer,
    safe_error_summary,
    select_cases,
    write_json_atomic,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / ".deer-flow" / "business-semantic-backbone-eval"
DEFAULT_TIMEOUT_SECONDS = 180.0


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def parse_business_semantic_backbone(value: str) -> dict[str, Any]:
    """Compatibility name retained for existing evaluation callers."""
    return parse_business_semantics(value)


def build_backbone_messages(*, question: str) -> list[object]:
    """Compatibility name retained for the sealed offline evaluation."""
    return build_semantic_messages(question)


async def run_backbone_case(
    *,
    model: AsyncModel,
    model_name: str,
    case: BrainEvalCase,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        message = await asyncio.wait_for(
            model.ainvoke(build_backbone_messages(question=case.question)),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        raise TimeoutError(f"backbone provider call exceeded {timeout_seconds:g} seconds for {case.case_id}") from exc
    if not isinstance(message, AIMessage):
        raise TypeError("business semantic model must return AIMessage")
    visible_answer, usage = extract_visible_answer(message)
    if not visible_answer:
        raise RuntimeError(f"empty business semantic backbone for {case.case_id}")
    backbone = parse_business_semantics(visible_answer)
    reasoning = extract_provider_reasoning(message)
    return {
        "case_id": case.case_id,
        "business_shape": case.business_shape,
        "review_status": case.review_status,
        "question": case.question,
        "question_sha256": _sha256_text(case.question),
        "model": model_name,
        "business_semantic_backbone": backbone,
        "visible_answer_sha256": _sha256_text(visible_answer),
        "provider_reasoning_present": bool(reasoning),
        "provider_reasoning_sha256": _sha256_text(reasoning) if reasoning else None,
        "usage": usage,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-.")
    if not normalized:
        raise ValueError("run id cannot be empty")
    return normalized


async def run_evaluation(args: argparse.Namespace) -> Path:
    if not args.execute:
        raise ValueError("live model evaluation requires the explicit --execute flag")
    cases = select_cases(default_cases(), args.case_ids)
    if args.max_calls != len(cases):
        raise ValueError(f"--max-calls must equal the sealed call count {len(cases)}")
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")

    config = get_app_config()
    model = create_chat_model(
        name=args.model,
        thinking_enabled=True,
        attach_tracing=False,
        app_config=config,
    )
    output_dir = args.output_root / _slug(args.run_id)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    manifest = {
        "schema_version": 1,
        "run_id": args.run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "model": args.model,
        "thinking_enabled": True,
        "max_calls": args.max_calls,
        "timeout_seconds": args.timeout_seconds,
        "system_prompt_sha256": _sha256_text(BUSINESS_SEMANTIC_BACKBONE_SYSTEM_PROMPT),
        "cases": [
            {
                "case_id": case.case_id,
                "business_shape": case.business_shape,
                "review_status": case.review_status,
                "question_sha256": _sha256_text(case.question),
            }
            for case in cases
        ],
        "isolation": {
            "lead_called": False,
            "memory": False,
            "registered_skills": False,
            "tools": False,
            "mcp": False,
            "subagents": False,
            "llm_judge": False,
            "production_state_writes": False,
            "reasoning_content_persisted": False,
        },
    }
    write_json_atomic(output_dir / "manifest.json", manifest)

    records: list[dict[str, Any]] = []
    try:
        for case in cases:
            record = await run_backbone_case(
                model=model,
                model_name=args.model,
                case=case,
                timeout_seconds=args.timeout_seconds,
            )
            records.append(record)
            write_json_atomic(
                output_dir / "results.json",
                {"status": "running", "records": records},
            )
    except BaseException as exc:
        write_json_atomic(
            output_dir / "completion.json",
            {
                "status": "failed",
                "completed_calls": len(records),
                "error_type": type(exc).__name__,
                "error": safe_error_summary(exc),
            },
        )
        raise

    write_json_atomic(
        output_dir / "results.json",
        {"status": "completed", "records": records},
    )
    write_json_atomic(
        output_dir / "completion.json",
        {"status": "completed", "completed_calls": len(records)},
    )
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--case-id", dest="case_ids", action="append", required=True)
    parser.add_argument("--model", default="glm-5-2-260617")
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--execute", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir = asyncio.run(run_evaluation(args))
    print(output_dir)


if __name__ == "__main__":
    main()
