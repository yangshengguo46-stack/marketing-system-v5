"""Run a small, auditable incubation preflight through DeerFlow's real Lead Agent."""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from mcn_incubation.evaluation import EvalCase, load_eval_cases
from mcn_incubation.preflight import PreflightLedger, build_preflight_prompt

from deerflow.agents.lead_agent.prompt import SYSTEM_PROMPT_TEMPLATE
from deerflow.client import DeerFlowClient

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "incubation-eval-cases.jsonl"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / ".deer-flow" / "incubation-preflight"
DEFAULT_CASE_IDS = ("M01", "B01", "G01")


class ModelFallbackError(RuntimeError):
    """DeerFlow returned a provider-error message instead of a model answer."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


def select_cases(cases: Sequence[EvalCase], case_ids: Sequence[str]) -> tuple[EvalCase, ...]:
    by_id = {case.case_id: case for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise ValueError(f"unknown case ids: {missing}")
    return tuple(by_id[case_id] for case_id in case_ids)


def collect_final_response(
    client: Any,
    *,
    prompt: str,
    thread_id: str,
) -> tuple[str, dict[str, int | float]]:
    """Collect the final AI message and normalized token usage from one stream."""

    chunks: dict[str, list[str]] = {}
    last_id = ""
    usage: dict[str, int | float] = {}
    fallback_error_code: str | None = None
    for event in client.stream(prompt, thread_id=thread_id):
        if event.type == "messages-tuple" and event.data.get("type") == "ai":
            message_id = str(event.data.get("id") or "")
            content = event.data.get("content", "")
            if isinstance(content, str) and content:
                chunks.setdefault(message_id, []).append(content)
                last_id = message_id
            additional = event.data.get("additional_kwargs", {})
            if isinstance(additional, dict) and additional.get("deerflow_error_fallback") is True:
                reason = str(additional.get("error_reason") or "error_fallback")
                safe_reason = re.sub(r"[^a-z0-9_]+", "_", reason.casefold()).strip("_")
                fallback_error_code = f"llm_{safe_reason or 'error_fallback'}"
        elif event.type == "end":
            raw_usage = event.data.get("usage", {})
            if isinstance(raw_usage, dict):
                usage = {name: value for name, value in raw_usage.items() if isinstance(name, str) and isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0}
    if fallback_error_code is not None:
        raise ModelFallbackError(fallback_error_code)
    return "".join(chunks.get(last_id, ())).strip(), usage


def _error_code(error: Exception) -> str:
    name = error.__class__.__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", dest="case_ids", action="append", help="Versioned case id; repeat for multiple cases")
    parser.add_argument("--include-mutations", action="store_true", help="Also run each case with its new-evidence mutation")
    parser.add_argument("--model", help="Configured DeerFlow model name; defaults to the first configured model")
    parser.add_argument("--thinking", action="store_true", help="Enable model thinking for this pinned run")
    parser.add_argument("--run-id", help="Single path-safe run id; defaults to a UTC timestamp")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required acknowledgement that this command will make paid model calls",
    )
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute is required because the preflight makes paid model calls")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    cases = load_eval_cases(args.corpus)
    selected = select_cases(cases, tuple(args.case_ids or DEFAULT_CASE_IDS))
    phases = (False, True) if args.include_mutations else (False,)
    trial_ids = tuple(f"{case.case_id}:{'mutation' if mutation else 'initial'}" for case in selected for mutation in phases)
    run_id = args.run_id or datetime.now(UTC).strftime("preflight-%Y%m%dT%H%M%SZ")

    client = DeerFlowClient(
        model_name=args.model,
        thinking_enabled=args.thinking,
        subagent_enabled=False,
        plan_mode=False,
        available_skills=set(),
        environment="incubation-preflight",
    )
    configured_models = client.list_models()["models"]
    model_id = args.model or str(configured_models[0]["name"])
    corpus_sha256 = sha256(args.corpus.read_bytes()).hexdigest()
    system_prompt_sha256 = sha256(SYSTEM_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
    ledger = PreflightLedger(args.output_root)
    ledger.create_run(
        run_id=run_id,
        model_id=model_id,
        trial_ids=trial_ids,
        system_prompt_sha256=system_prompt_sha256,
        corpus_sha256=corpus_sha256,
        created_at=datetime.now(UTC),
    )

    for case in selected:
        for include_mutation in phases:
            phase = "mutation" if include_mutation else "initial"
            trial_id = f"{case.case_id}:{phase}"
            prompt = build_preflight_prompt(case, include_mutation=include_mutation)
            started_at = datetime.now(UTC)
            try:
                output, usage = collect_final_response(
                    client,
                    prompt=prompt,
                    thread_id=f"incubation-{run_id}-{case.case_id}-{phase}",
                )
                completed_at = datetime.now(UTC)
                if not output:
                    ledger.record_failure(
                        run_id=run_id,
                        trial_id=trial_id,
                        prompt=prompt,
                        error_code="empty_model_output",
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                    print(f"{trial_id}: failed (empty_model_output)")
                    continue
                ledger.record_success(
                    run_id=run_id,
                    trial_id=trial_id,
                    prompt=prompt,
                    output=output,
                    started_at=started_at,
                    completed_at=completed_at,
                    usage=usage,
                )
                print(f"{trial_id}: succeeded")
            except Exception as error:
                completed_at = datetime.now(UTC)
                code = error.error_code if isinstance(error, ModelFallbackError) else _error_code(error)
                ledger.record_failure(
                    run_id=run_id,
                    trial_id=trial_id,
                    prompt=prompt,
                    error_code=code,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                print(f"{trial_id}: failed ({code})")

    completion = ledger.complete_run(run_id, completed_at=datetime.now(UTC))
    ledger.verify_run(run_id)
    print(f"run={run_id} status={completion.status} succeeded={completion.succeeded} failed={completion.failed}")
    print(f"evidence={args.output_root / run_id}")
    return 0 if completion.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
