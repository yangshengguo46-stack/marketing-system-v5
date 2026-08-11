"""Run a capped same-model comparison of the experimental content-territory method."""

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
from mcn_incubation.preflight import PreflightLedger
from mcn_incubation.territory_evaluation import (
    COMMON_SYSTEM_CONTEXT,
    NATURAL_RESPONSE_CONTRACT,
    OUTPUT_CONTRACT,
    TERRITORY_METHOD_CARD,
    TERRITORY_METHOD_V2_CARD,
    ResponseMode,
    TerritoryAnchorCase,
    TerritoryContrastCase,
    TerritoryEvalVariant,
    default_territory_mechanism_library,
    load_territory_anchor_cases,
    load_territory_contrast_cases,
    render_anchor_evidence_message,
    render_anchor_message,
    render_case_evidence_message,
    render_case_message,
    render_mechanism_context,
    render_system_context,
    render_territory_explorer_context,
)

from deerflow.config import get_app_config
from deerflow.models.factory import create_chat_model

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "marketing-territory-contrast-cases.jsonl"
DEFAULT_ANCHOR_CORPUS = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "marketing-territory-eval-cases.jsonl"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / ".deer-flow" / "marketing-territory-bakeoff"
DEFAULT_CONTEXT_BUDGET_CHARS = 8_000
DEFAULT_SEED = 42


@dataclass(frozen=True, slots=True)
class PreparedTerritoryTrial:
    trial_id: str
    case: TerritoryContrastCase | TerritoryAnchorCase
    variant: TerritoryEvalVariant
    response_mode: ResponseMode
    model_call_count: int
    exploration_message: str | None
    system_context: str
    user_message: str
    estimated_chars: int
    context_budget_chars: int


def select_contrast_groups(
    cases: Sequence[TerritoryContrastCase],
    groups: Sequence[str],
) -> tuple[TerritoryContrastCase, ...]:
    if not groups:
        raise ValueError("at least one contrast group is required")
    if len(set(groups)) != len(groups):
        raise ValueError("contrast groups must be unique")
    available = {case.contrast_group for case in cases}
    missing = [group for group in groups if group not in available]
    if missing:
        raise ValueError(f"unknown contrast groups: {missing}")
    selected = tuple(case for case in cases if case.contrast_group in groups)
    for group in groups:
        if sum(case.contrast_group == group for case in selected) < 2:
            raise ValueError(f"contrast group must contain at least two cases: {group}")
    return selected


def select_anchor_cases(
    cases: Sequence[TerritoryAnchorCase],
    case_ids: Sequence[str],
) -> tuple[TerritoryAnchorCase, ...]:
    if not case_ids:
        raise ValueError("at least one anchor case id is required")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("anchor case ids must be unique")
    by_id = {case.case_id: case for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise ValueError(f"unknown anchor case ids: {missing}")
    return tuple(by_id[case_id] for case_id in case_ids)


def prepare_trials(
    *,
    cases: Sequence[TerritoryContrastCase],
    variants: Sequence[TerritoryEvalVariant],
    context_budget_chars: int,
    seed: int,
    include_mutation: bool,
    response_mode: ResponseMode = ResponseMode.STRUCTURED_JSON,
) -> tuple[PreparedTerritoryTrial, ...]:
    if not cases:
        raise ValueError("at least one territory case is required")
    if not variants:
        raise ValueError("at least one territory variant is required")
    if context_budget_chars < 1_000:
        raise ValueError("context budget must be at least 1000 characters")
    trials: list[PreparedTerritoryTrial] = []
    phase = "revision" if include_mutation else "initial"
    for case in cases:
        evidence_message = render_case_evidence_message(
            case,
            include_mutation=include_mutation,
        )
        user_message = render_case_message(
            case,
            include_mutation=include_mutation,
            response_mode=response_mode,
        )
        for variant in variants:
            system_context = render_system_context(
                variant,
                mechanism_query=user_message,
            )
            estimated_chars = len(system_context) + len(user_message)
            if estimated_chars > context_budget_chars:
                raise ValueError(f"territory trial exceeds context budget: {case.case_id}:{variant.value} uses {estimated_chars} of {context_budget_chars} characters")
            exploration_message = evidence_message if variant is TerritoryEvalVariant.TERRITORY_TWO_PASS_MECHANISMS else None
            if exploration_message is not None:
                exploration_chars = len(render_territory_explorer_context(exploration_message)) + len(exploration_message)
                if exploration_chars > context_budget_chars:
                    raise ValueError(f"territory exploration exceeds context budget: {case.case_id} uses {exploration_chars} of {context_budget_chars} characters")
            trials.append(
                PreparedTerritoryTrial(
                    trial_id=f"{case.case_id}:{phase}:{variant.value}",
                    case=case,
                    variant=variant,
                    response_mode=response_mode,
                    model_call_count=(2 if variant is TerritoryEvalVariant.TERRITORY_TWO_PASS_MECHANISMS else 1),
                    exploration_message=exploration_message,
                    system_context=system_context,
                    user_message=user_message,
                    estimated_chars=estimated_chars,
                    context_budget_chars=context_budget_chars,
                )
            )
    if len({trial.trial_id for trial in trials}) != len(trials):
        raise ValueError("prepared territory trial ids must be unique")
    random.Random(seed).shuffle(trials)
    return tuple(trials)


def prepare_anchor_trials(
    *,
    cases: Sequence[TerritoryAnchorCase],
    variants: Sequence[TerritoryEvalVariant],
    context_budget_chars: int,
    seed: int,
    include_mutation: bool,
    response_mode: ResponseMode = ResponseMode.NATURAL_JUDGMENT,
) -> tuple[PreparedTerritoryTrial, ...]:
    if not cases:
        raise ValueError("at least one territory anchor is required")
    if not variants:
        raise ValueError("at least one territory variant is required")
    if context_budget_chars < 1_000:
        raise ValueError("context budget must be at least 1000 characters")
    trials: list[PreparedTerritoryTrial] = []
    phase = "revision" if include_mutation else "initial"
    for case in cases:
        evidence_message = render_anchor_evidence_message(
            case,
            include_mutation=include_mutation,
        )
        user_message = render_anchor_message(
            case,
            include_mutation=include_mutation,
            response_mode=response_mode,
        )
        for variant in variants:
            system_context = render_system_context(
                variant,
                mechanism_query=user_message,
            )
            estimated_chars = len(system_context) + len(user_message)
            if estimated_chars > context_budget_chars:
                raise ValueError(f"territory trial exceeds context budget: {case.case_id}:{variant.value} uses {estimated_chars} of {context_budget_chars} characters")
            exploration_message = evidence_message if variant is TerritoryEvalVariant.TERRITORY_TWO_PASS_MECHANISMS else None
            if exploration_message is not None:
                exploration_chars = len(render_territory_explorer_context(exploration_message)) + len(exploration_message)
                if exploration_chars > context_budget_chars:
                    raise ValueError(f"territory exploration exceeds context budget: {case.case_id} uses {exploration_chars} of {context_budget_chars} characters")
            trials.append(
                PreparedTerritoryTrial(
                    trial_id=f"{case.case_id}:{phase}:{variant.value}",
                    case=case,
                    variant=variant,
                    response_mode=response_mode,
                    model_call_count=(2 if variant is TerritoryEvalVariant.TERRITORY_TWO_PASS_MECHANISMS else 1),
                    exploration_message=exploration_message,
                    system_context=system_context,
                    user_message=user_message,
                    estimated_chars=estimated_chars,
                    context_budget_chars=context_budget_chars,
                )
            )
    if len({trial.trial_id for trial in trials}) != len(trials):
        raise ValueError("prepared territory trial ids must be unique")
    random.Random(seed).shuffle(trials)
    return tuple(trials)


def enforce_paid_trial_cap(*, trial_count: int, max_paid_trials: int) -> None:
    if max_paid_trials < 1:
        raise ValueError("paid trial cap must be positive")
    if trial_count > max_paid_trials:
        raise ValueError(f"paid trial cap is {max_paid_trials}, but selection contains {trial_count} trials")


def count_paid_calls(trials: Sequence[PreparedTerritoryTrial]) -> int:
    return sum(trial.model_call_count for trial in trials)


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        text = block.get("text") if isinstance(block, Mapping) else getattr(block, "text", None)
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


def _sealed_trial_input(
    trial: PreparedTerritoryTrial,
    *,
    model_id: str,
    thinking_enabled: bool,
    exploration_system: str | None = None,
    exploration_output: str | None = None,
    final_system_context: str | None = None,
) -> str:
    decision_system = final_system_context or trial.system_context
    value = {
        "case_id": trial.case.case_id,
        "context_budget_chars": trial.context_budget_chars,
        "estimated_context_chars": trial.estimated_chars,
        "messages": [
            {"content": decision_system, "role": "system"},
            {"content": trial.user_message, "role": "user"},
        ],
        "model_id": model_id,
        "response_mode": trial.response_mode.value,
        "thinking_enabled": thinking_enabled,
        "trial_id": trial.trial_id,
        "variant": trial.variant.value,
    }
    if exploration_system is not None:
        if trial.exploration_message is None:
            raise ValueError("exploration system requires a prepared exploration message")
        value["exploration"] = {
            "messages": [
                {"content": exploration_system, "role": "system"},
                {"content": trial.exploration_message, "role": "user"},
            ],
            "output": exploration_output,
        }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _lead_context_with_exploration(base_context: str, exploration_output: str) -> str:
    encoded = json.dumps(exploration_output, ensure_ascii=False)
    return f"""{base_context}

<read_only_territory_exploration encoding="json-string">
The following is advisory candidate material from a read-only exploration pass. You remain the
only decision-maker. Check it against supplied facts, reject unsupported claims, and do not
assume it is correct or complete.
{encoded}
</read_only_territory_exploration>"""


def _combine_usage(
    exploration: Mapping[str, int | float],
    decision: Mapping[str, int | float],
) -> dict[str, int | float]:
    combined = {
        **{f"exploration_{name}": value for name, value in exploration.items()},
        **{f"decision_{name}": value for name, value in decision.items()},
    }
    exploration_total = exploration.get("total_tokens")
    decision_total = decision.get("total_tokens")
    if isinstance(exploration_total, (int, float)) and isinstance(decision_total, (int, float)):
        combined["total_tokens"] = exploration_total + decision_total
    return combined


def _error_code(error: Exception) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", error.__class__.__name__).lower()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--group",
        dest="groups",
        action="append",
        help="Complete contrast group; repeat to test more groups",
    )
    selection.add_argument(
        "--anchor-case",
        dest="anchor_case_ids",
        action="append",
        help="Expert anchor case id; repeat to test more anchors",
    )
    parser.add_argument(
        "--variant",
        dest="variants",
        action="append",
        choices=[variant.value for variant in TerritoryEvalVariant],
        required=True,
        help="Evaluation candidate; repeat for a comparison",
    )
    parser.add_argument("--max-paid-trials", type=int, required=True)
    parser.add_argument("--model", help="Configured DeerFlow model; defaults to the first model")
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--include-mutation", action="store_true")
    parser.add_argument(
        "--response-mode",
        choices=[mode.value for mode in ResponseMode],
        default=ResponseMode.STRUCTURED_JSON.value,
    )
    parser.add_argument("--context-budget-chars", type=int, default=DEFAULT_CONTEXT_BUDGET_CHARS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--run-id")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--anchor-corpus", type=Path, default=DEFAULT_ANCHOR_CORPUS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required acknowledgement that this command makes paid model calls",
    )
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute is required because the territory bakeoff makes paid model calls")
    if args.context_budget_chars < 1_000:
        parser.error("--context-budget-chars must be at least 1000")
    if args.max_paid_trials < 1:
        parser.error("--max-paid-trials must be positive")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    variants = tuple(TerritoryEvalVariant(value) for value in args.variants)
    response_mode = ResponseMode(args.response_mode)
    if args.anchor_case_ids is not None:
        corpus_path = args.anchor_corpus
        cases = select_anchor_cases(
            load_territory_anchor_cases(corpus_path),
            tuple(args.anchor_case_ids),
        )
        trials = prepare_anchor_trials(
            cases=cases,
            variants=variants,
            context_budget_chars=args.context_budget_chars,
            seed=args.seed,
            include_mutation=args.include_mutation,
            response_mode=response_mode,
        )
    else:
        corpus_path = args.corpus
        contrast_cases = select_contrast_groups(
            load_territory_contrast_cases(corpus_path),
            tuple(args.groups),
        )
        trials = prepare_trials(
            cases=contrast_cases,
            variants=variants,
            context_budget_chars=args.context_budget_chars,
            seed=args.seed,
            include_mutation=args.include_mutation,
            response_mode=response_mode,
        )
    enforce_paid_trial_cap(
        trial_count=count_paid_calls(trials),
        max_paid_trials=args.max_paid_trials,
    )

    app_config = get_app_config()
    model_id = args.model or app_config.models[0].name
    model = create_chat_model(
        name=model_id,
        thinking_enabled=args.thinking,
        app_config=app_config,
        attach_tracing=False,
    )
    created_at = datetime.now(UTC)
    run_id = args.run_id or created_at.strftime("territory-bakeoff-%Y%m%dT%H%M%SZ")
    ledger = PreflightLedger(args.output_root)
    mechanism_context = render_mechanism_context(default_territory_mechanism_library().cards)
    contract_text = f"{COMMON_SYSTEM_CONTEXT}\n{TERRITORY_METHOD_CARD}\n{TERRITORY_METHOD_V2_CARD}\n{mechanism_context}\n{OUTPUT_CONTRACT}\n{NATURAL_RESPONSE_CONTRACT}"
    ledger.create_run(
        run_id=run_id,
        model_id=model_id,
        trial_ids=tuple(trial.trial_id for trial in trials),
        system_prompt_sha256=sha256(contract_text.encode("utf-8")).hexdigest(),
        corpus_sha256=sha256(corpus_path.read_bytes()).hexdigest(),
        created_at=created_at,
    )

    for trial in trials:
        exploration_system: str | None = None
        exploration_output: str | None = None
        final_system_context = trial.system_context
        sealed_input = _sealed_trial_input(
            trial,
            model_id=model_id,
            thinking_enabled=args.thinking,
        )
        started_at = datetime.now(UTC)
        try:
            exploration_usage: dict[str, int | float] = {}
            if trial.variant is TerritoryEvalVariant.TERRITORY_TWO_PASS_MECHANISMS:
                if trial.exploration_message is None:
                    raise ValueError("two-pass trial has no exploration message")
                exploration_system = render_territory_explorer_context(trial.exploration_message)
                sealed_input = _sealed_trial_input(
                    trial,
                    model_id=model_id,
                    thinking_enabled=args.thinking,
                    exploration_system=exploration_system,
                )
                exploration_message = model.invoke(
                    [
                        SystemMessage(content=exploration_system),
                        HumanMessage(content=trial.exploration_message),
                    ]
                )
                exploration_output, exploration_usage = extract_model_response(exploration_message)
                if not exploration_output:
                    completed_at = datetime.now(UTC)
                    ledger.record_failure(
                        run_id=run_id,
                        trial_id=trial.trial_id,
                        prompt=sealed_input,
                        error_code="empty_exploration_output",
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                    print(f"{trial.trial_id}: failed (empty_exploration_output)")
                    continue
                final_system_context = _lead_context_with_exploration(
                    trial.system_context,
                    exploration_output,
                )
                sealed_input = _sealed_trial_input(
                    trial,
                    model_id=model_id,
                    thinking_enabled=args.thinking,
                    exploration_system=exploration_system,
                    exploration_output=exploration_output,
                    final_system_context=final_system_context,
                )
            message = model.invoke(
                [
                    SystemMessage(content=final_system_context),
                    HumanMessage(content=trial.user_message),
                ]
            )
            output, usage = extract_model_response(message)
            if exploration_usage:
                usage = _combine_usage(exploration_usage, usage)
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
