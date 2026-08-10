"""Run a capped real-model comparison of incubation context candidates."""

from __future__ import annotations

import argparse
import json
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from mcn_incubation.context import (
    LEAD_AGENT_CONSTITUTION,
    ArchitectureVariant,
    ContextAssembler,
    ContextBundle,
    ContextRequest,
)
from mcn_incubation.domain import IncubationBrief, ProjectTruth, TruthKind
from mcn_incubation.evaluation import EvalCase, load_eval_cases
from mcn_incubation.memory import CaseMemory
from mcn_incubation.methods import default_method_library
from mcn_incubation.preflight import PreflightLedger, build_preflight_prompt

from deerflow.config import get_app_config
from deerflow.models.factory import create_chat_model

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "incubation-eval-cases.jsonl"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / ".deer-flow" / "incubation-micro-bakeoff"
DEFAULT_CONTEXT_BUDGET_CHARS = 12_000
DEFAULT_SEED = 42

_FINAL_USER_MESSAGE = "请直接给出最终孵化判断。让读者能够区分已知事实、暂定选择、关键未知、替代方案和最小验证实验；不要介绍内部方法或上下文结构。"


@dataclass(frozen=True, slots=True)
class PreparedTrial:
    trial_id: str
    case: EvalCase
    variant: ArchitectureVariant
    bundle: ContextBundle
    user_message: str


def _context_request(case: EvalCase, *, created_at: datetime) -> ContextRequest:
    if len(case.facts) != len(case.truth_ids):
        raise ValueError(f"case facts and truth ids must align: {case.case_id}")
    project_id = f"eval-{case.case_id.casefold()}"
    truths = tuple(
        ProjectTruth(
            truth_id=truth_id,
            owner_id="eval-owner",
            project_id=project_id,
            kind=TruthKind.USER_FACT,
            statement=fact,
            source_ref=f"eval-case:{case.case_id}",
            created_at=created_at,
        )
        for truth_id, fact in zip(case.truth_ids, case.facts, strict=True)
    )
    prompt = build_preflight_prompt(case, include_mutation=False)
    brief = IncubationBrief(
        brief_version_id=f"{project_id}-brief-v1",
        brief_id=f"{project_id}-brief",
        version=1,
        owner_id="eval-owner",
        project_id=project_id,
        created_at=created_at,
        subject_kind=case.subject_kind,
        subject_summary=case.scenario,
        available_assets=case.facts,
        offers=case.offers,
        constraints=case.constraints,
        goals=case.goals,
        truth_ids=case.truth_ids,
    )
    return ContextRequest(
        prompt=prompt,
        brief=brief,
        truths=truths,
        method_query=" ".join(case.required_capabilities),
    )


def prepare_trials(
    *,
    cases: Sequence[EvalCase],
    variants: Sequence[ArchitectureVariant],
    context_budget_chars: int,
    seed: int,
    created_at: datetime,
) -> tuple[PreparedTrial, ...]:
    """Build candidate contexts and randomize execution without calling a model."""

    if not cases:
        raise ValueError("at least one case is required")
    if not variants:
        raise ValueError("at least one architecture variant is required")
    if ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH_CASES in variants:
        raise ValueError("reviewed case memory is required before testing the case-memory candidate")
    assembler = ContextAssembler(
        method_library=default_method_library(),
        case_memory=CaseMemory(()),
        max_context_chars=context_budget_chars,
    )
    trials = [
        PreparedTrial(
            trial_id=f"{case.case_id}:{variant.value}",
            case=case,
            variant=variant,
            bundle=assembler.assemble(
                variant=variant,
                request=_context_request(case, created_at=created_at),
            ),
            user_message=_FINAL_USER_MESSAGE,
        )
        for case in cases
        for variant in variants
    ]
    if len({trial.trial_id for trial in trials}) != len(trials):
        raise ValueError("prepared trial ids must be unique")
    random.Random(seed).shuffle(trials)
    return tuple(trials)


def enforce_paid_trial_cap(*, trial_count: int, max_paid_trials: int) -> None:
    if max_paid_trials < 1:
        raise ValueError("paid trial cap must be positive")
    if trial_count > max_paid_trials:
        raise ValueError(f"paid trial cap is {max_paid_trials}, but selection contains {trial_count} trials")


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, Mapping):
            text = block.get("text")
        else:
            text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts).strip()


def extract_model_response(message: Any) -> tuple[str, dict[str, int | float]]:
    output = _message_text(getattr(message, "content", ""))
    raw_usage = getattr(message, "usage_metadata", None)
    if not isinstance(raw_usage, Mapping):
        raw_usage = {}
    usage = {str(name): value for name, value in raw_usage.items() if isinstance(name, str) and isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0}
    return output, usage


def _select_cases(cases: Sequence[EvalCase], case_ids: Sequence[str]) -> tuple[EvalCase, ...]:
    by_id = {case.case_id: case for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise ValueError(f"unknown case ids: {missing}")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("case ids must be unique")
    return tuple(by_id[case_id] for case_id in case_ids)


def _sealed_trial_input(
    trial: PreparedTrial,
    *,
    model_id: str,
    thinking_enabled: bool,
) -> str:
    value = {
        "case_id": trial.case.case_id,
        "context_budget_chars": trial.bundle.context_budget_chars,
        "estimated_context_chars": trial.bundle.estimated_chars,
        "messages": [
            {"content": trial.bundle.rendered_context, "role": "system"},
            {"content": trial.user_message, "role": "user"},
        ],
        "model_id": model_id,
        "thinking_enabled": thinking_enabled,
        "trial_id": trial.trial_id,
        "variant": trial.variant.value,
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _error_code(error: Exception) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", error.__class__.__name__).lower()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", dest="case_ids", action="append", required=True, help="Versioned case id; repeat to compare more cases")
    parser.add_argument(
        "--variant",
        dest="variants",
        action="append",
        choices=[variant.value for variant in ArchitectureVariant],
        required=True,
        help="Architecture candidate; repeat to compare candidates",
    )
    parser.add_argument("--max-paid-trials", type=int, required=True, help="Hard upper bound for external model calls")
    parser.add_argument("--model", help="Configured DeerFlow model; defaults to the first configured model")
    parser.add_argument("--thinking", action="store_true", help="Enable the configured model's native thinking mode")
    parser.add_argument("--context-budget-chars", type=int, default=DEFAULT_CONTEXT_BUDGET_CHARS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--run-id", help="Single path-safe run id; defaults to a UTC timestamp")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--execute", action="store_true", help="Required acknowledgement that the command makes paid model calls")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute is required because the micro bakeoff makes paid model calls")
    if args.context_budget_chars < 1_000:
        parser.error("--context-budget-chars must be at least 1000")
    if args.max_paid_trials < 1:
        parser.error("--max-paid-trials must be positive")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    corpus = load_eval_cases(args.corpus)
    cases = _select_cases(corpus, tuple(args.case_ids))
    variants = tuple(ArchitectureVariant(value) for value in args.variants)
    created_at = datetime.now(UTC)
    trials = prepare_trials(
        cases=cases,
        variants=variants,
        context_budget_chars=args.context_budget_chars,
        seed=args.seed,
        created_at=created_at,
    )
    enforce_paid_trial_cap(trial_count=len(trials), max_paid_trials=args.max_paid_trials)

    app_config = get_app_config()
    model_id = args.model or app_config.models[0].name
    model = create_chat_model(
        name=model_id,
        thinking_enabled=args.thinking,
        app_config=app_config,
        attach_tracing=False,
    )
    run_id = args.run_id or datetime.now(UTC).strftime("micro-bakeoff-%Y%m%dT%H%M%SZ")
    ledger = PreflightLedger(args.output_root)
    contract_text = f"{LEAD_AGENT_CONSTITUTION}\n{_FINAL_USER_MESSAGE}"
    ledger.create_run(
        run_id=run_id,
        model_id=model_id,
        trial_ids=tuple(trial.trial_id for trial in trials),
        system_prompt_sha256=sha256(contract_text.encode("utf-8")).hexdigest(),
        corpus_sha256=sha256(args.corpus.read_bytes()).hexdigest(),
        created_at=created_at,
    )

    for trial in trials:
        sealed_input = _sealed_trial_input(
            trial,
            model_id=model_id,
            thinking_enabled=args.thinking,
        )
        started_at = datetime.now(UTC)
        try:
            message = model.invoke(
                [
                    SystemMessage(content=trial.bundle.rendered_context),
                    HumanMessage(content=trial.user_message),
                ]
            )
            output, usage = extract_model_response(message)
            completed_at = datetime.now(UTC)
            if not output:
                ledger.record_failure(
                    run_id=run_id,
                    trial_id=trial.trial_id,
                    prompt=sealed_input,
                    error_code="empty_model_output",
                    started_at=started_at,
                    completed_at=completed_at,
                )
                print(f"{trial.trial_id}: failed (empty_model_output)")
                continue
            ledger.record_success(
                run_id=run_id,
                trial_id=trial.trial_id,
                prompt=sealed_input,
                output=output,
                started_at=started_at,
                completed_at=completed_at,
                usage=usage,
            )
            print(f"{trial.trial_id}: succeeded")
        except Exception as error:
            completed_at = datetime.now(UTC)
            code = _error_code(error)
            ledger.record_failure(
                run_id=run_id,
                trial_id=trial.trial_id,
                prompt=sealed_input,
                error_code=code,
                started_at=started_at,
                completed_at=completed_at,
            )
            print(f"{trial.trial_id}: failed ({code})")

    completion = ledger.complete_run(run_id, completed_at=datetime.now(UTC))
    ledger.verify_run(run_id)
    print(f"run={run_id} status={completion.status} succeeded={completion.succeeded} failed={completion.failed}")
    print(f"evidence={args.output_root / run_id}")
    return 0 if completion.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
