"""Run capped incubation evaluations through DeerFlow's real Lead Agent and tools."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.checkpoint.memory import InMemorySaver
from mcn_incubation.agent_evaluation import (
    AgentEventCollector,
    AgentTraceLedger,
    AgentTrialTrace,
)
from mcn_incubation.domain import (
    EvidenceItem,
    EvidenceKind,
    EvidenceStatus,
    IncubationProject,
    ProjectTruth,
    TruthKind,
)
from mcn_incubation.evaluation import EvalCase, load_eval_cases
from mcn_incubation.persistence import IncubationRepository
from mcn_incubation.persistence_schema import bootstrap_incubation_schema
from mcn_incubation.preflight import PreflightLedger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from deerflow.agents.lead_agent.prompt import SYSTEM_PROMPT_TEMPLATE
from deerflow.client import DeerFlowClient

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "incubation-eval-cases.jsonl"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / ".deer-flow" / "incubation-agent-eval"
_REQUIRED_INCUBATION_TOOLS = frozenset(
    {
        "incubation_context",
        "incubation_project_context",
        "incubation_project_evidence",
    }
)


@dataclass(frozen=True, slots=True)
class AgentEvalTrialSpec:
    trial_id: str
    project_id: str
    case: EvalCase
    include_mutation: bool


def _safe_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    if not normalized:
        raise ValueError("identifier cannot normalize to an empty path component")
    return normalized


def prepare_trial_specs(
    *,
    cases: Sequence[EvalCase],
    include_mutations: bool,
    run_id: str,
) -> tuple[AgentEvalTrialSpec, ...]:
    if not cases:
        raise ValueError("at least one case is required")
    run_component = _safe_component(run_id)
    phases = (False, True) if include_mutations else (False,)
    trials = tuple(
        AgentEvalTrialSpec(
            trial_id=f"{case.case_id}:{'mutation' if mutation else 'initial'}",
            project_id=(f"agent-eval-{run_component}-{_safe_component(case.case_id)}-{'mutation' if mutation else 'initial'}"),
            case=case,
            include_mutation=mutation,
        )
        for case in cases
        for mutation in phases
    )
    if len({trial.trial_id for trial in trials}) != len(trials):
        raise ValueError("agent evaluation trial ids must be unique")
    if len({trial.project_id for trial in trials}) != len(trials):
        raise ValueError("agent evaluation project ids must be unique")
    if any(len(trial.project_id) > 255 for trial in trials):
        raise ValueError("agent evaluation project id exceeds storage limit")
    return trials


def build_agent_eval_prompt(trial: AgentEvalTrialSpec) -> str:
    sections = [
        "请为系统中已经存在的 MCN 孵化项目做一次首轮业务判断。",
        f"项目 ID：{trial.project_id}",
        "请基于系统保存的项目资料，判断主体适合怎么起号、采用什么表现形式、持续做什么内容、如何形成变现与转化闭环，并给出最小验证实验。",
        "区分已知事实、外部证据、暂定选择、关键未知和替代方案；信息不足时可以继续做暂定判断，但不得补造身份、资产、效果、客户、渠道、产能、价格、预算或指标阈值。",
    ]
    if trial.include_mutation:
        sections.append("这是新增证据后的独立修订轮次；请指出哪些原判断应当改变、保留或继续未知。")
    return "\n".join(sections)


def _trial_truth_statements(trial: AgentEvalTrialSpec) -> tuple[tuple[str, TruthKind, str], ...]:
    case = trial.case
    statements: list[tuple[str, TruthKind, str]] = [("scenario", TruthKind.USER_FACT, case.scenario)]
    statements.extend(
        (f"fact-{index}-{truth_id}", TruthKind.USER_FACT, fact)
        for index, (truth_id, fact) in enumerate(
            zip(case.truth_ids, case.facts, strict=True),
            start=1,
        )
    )
    statements.extend((f"constraint-{index}", TruthKind.USER_FACT, f"现实限制：{value}") for index, value in enumerate(case.constraints, start=1))
    statements.extend((f"goal-{index}", TruthKind.USER_FACT, f"经营目标：{value}") for index, value in enumerate(case.goals, start=1))
    statements.extend((f"offer-{index}", TruthKind.USER_FACT, f"当前产品或服务：{value}") for index, value in enumerate(case.offers, start=1))
    if trial.include_mutation:
        statements.append(
            (
                "mutation",
                TruthKind.SOURCE_FACT,
                f"新补充证据：{case.mutation}",
            )
        )
    return tuple(statements)


async def seed_trial_state(
    *,
    repository: IncubationRepository,
    trial: AgentEvalTrialSpec,
    owner_id: str,
    corpus_sha256: str,
    created_at: datetime,
) -> None:
    if len(trial.case.facts) != len(trial.case.truth_ids):
        raise ValueError(f"case facts and truth ids must align: {trial.case.case_id}")
    statements = _trial_truth_statements(trial)
    evidence_id = f"{trial.project_id}-input-evidence"
    source_payload = {
        "case_id": trial.case.case_id,
        "include_mutation": trial.include_mutation,
        "statements": [statement for _suffix, _kind, statement in statements],
        "corpus_sha256": corpus_sha256,
    }
    content_hash = sha256(
        json.dumps(
            source_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    await repository.create_project(
        IncubationProject(
            project_id=trial.project_id,
            owner_id=owner_id,
            working_title=trial.case.scenario,
            subject_kind=trial.case.subject_kind,
            created_at=created_at,
        ),
        operation_key=f"{trial.project_id}-create",
    )
    await repository.append_evidence(
        EvidenceItem(
            evidence_id=evidence_id,
            owner_id=owner_id,
            project_id=trial.project_id,
            kind=EvidenceKind.USER_ARTIFACT,
            status=EvidenceStatus.ACTIVE,
            source_locator=(f"eval-corpus://incubation-eval-cases/{trial.case.case_id}"),
            captured_at=created_at,
            content_hash=content_hash,
            observed_facts=tuple(statement for _suffix, _kind, statement in statements),
            limitations=("这是版本化评测输入，不是账号实际经营结果，也不能证明某条孵化路线有效。",),
            artifact_refs=(f"corpus-sha256:{corpus_sha256}",),
            source_updated_label=f"corpus-sha256:{corpus_sha256}",
        ),
        operation_key=f"{trial.project_id}-append-evidence",
    )
    for suffix, kind, statement in statements:
        truth_id = f"{trial.project_id}-{suffix}"
        await repository.append_truth(
            ProjectTruth(
                truth_id=truth_id,
                owner_id=owner_id,
                project_id=trial.project_id,
                kind=kind,
                statement=statement,
                created_at=created_at,
                source_ref=evidence_id,
                evidence_refs=(evidence_id,),
            ),
            operation_key=f"{trial.project_id}-append-{suffix}",
        )


def enforce_paid_trial_cap(*, trial_count: int, max_paid_trials: int) -> None:
    if max_paid_trials < 1:
        raise ValueError("paid trial cap must be positive")
    if trial_count > max_paid_trials:
        raise ValueError(f"paid trial cap is {max_paid_trials}, but selection contains {trial_count} trials")


def _select_cases(
    cases: Sequence[EvalCase],
    case_ids: Sequence[str],
) -> tuple[EvalCase, ...]:
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("case ids must be unique")
    by_id = {case.case_id: case for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise ValueError(f"unknown case ids: {missing}")
    return tuple(by_id[case_id] for case_id in case_ids)


def _tool_surface(client: DeerFlowClient, *, model_name: str) -> list[dict[str, Any]]:
    tools = client._get_tools(model_name=model_name, subagent_enabled=False)
    schemas_by_name = {tool.name: convert_to_openai_tool(tool) for tool in tools}
    missing = _REQUIRED_INCUBATION_TOOLS - schemas_by_name.keys()
    if missing:
        raise RuntimeError(f"required incubation tools are missing: {sorted(missing)}")
    return [schemas_by_name[name] for name in sorted(schemas_by_name)]


@contextmanager
def _bind_evaluation_session_factory(session_factory) -> Iterator[None]:
    module_names = (
        "deerflow.tools.builtins.incubation_project_context_tool",
        "deerflow.tools.builtins.incubation_project_evidence_tool",
    )
    modules = [importlib.import_module(name) for name in module_names]
    originals = [module.get_session_factory for module in modules]
    try:
        for module in modules:
            module.get_session_factory = lambda: session_factory
        yield
    finally:
        for module, original in zip(modules, originals, strict=True):
            module.get_session_factory = original


def _error_code(error: Exception) -> str:
    name = error.__class__.__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        dest="case_ids",
        action="append",
        required=True,
        help="Versioned case id; repeat for multiple cases",
    )
    parser.add_argument(
        "--include-mutations",
        action="store_true",
        help="Create a separate project and trial with each case's new evidence",
    )
    parser.add_argument(
        "--max-paid-trials",
        type=int,
        required=True,
        help="Hard upper bound for selected agent trials",
    )
    parser.add_argument(
        "--max-agent-steps",
        type=int,
        required=True,
        help="LangGraph recursion limit per trial; bounds loops but is not a currency cap",
    )
    parser.add_argument(
        "--model",
        help="Configured DeerFlow model; defaults to the first configured model",
    )
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="Enable the configured model's native thinking mode",
    )
    parser.add_argument(
        "--run-id",
        help="Single path-safe run id; defaults to a UTC timestamp",
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required acknowledgement that full Agent trials make paid model calls",
    )
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute is required because Agent evaluation makes paid model calls")
    if args.max_paid_trials < 1:
        parser.error("--max-paid-trials must be positive")
    if not 4 <= args.max_agent_steps <= 50:
        parser.error("--max-agent-steps must be between 4 and 50")
    return args


def _write_database_digest(database_path: Path) -> None:
    digest_path = database_path.with_suffix(database_path.suffix + ".sha256")
    digest_text = sha256(database_path.read_bytes()).hexdigest() + "\n"
    try:
        with digest_path.open("x", encoding="utf-8") as handle:
            handle.write(digest_text)
    except FileExistsError:
        if digest_path.read_text(encoding="utf-8") != digest_text:
            raise RuntimeError("agent evaluation database digest already differs") from None


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    corpus = load_eval_cases(args.corpus)
    cases = _select_cases(corpus, tuple(args.case_ids))
    run_id = args.run_id or datetime.now(UTC).strftime("agent-eval-%Y%m%dT%H%M%SZ")
    trials = prepare_trial_specs(
        cases=cases,
        include_mutations=args.include_mutations,
        run_id=run_id,
    )
    enforce_paid_trial_cap(
        trial_count=len(trials),
        max_paid_trials=args.max_paid_trials,
    )

    created_at = datetime.now(UTC)
    corpus_sha256 = sha256(args.corpus.read_bytes()).hexdigest()
    actor_id = f"agent-eval-owner-{_safe_component(run_id)}"
    actor_sha256 = sha256(actor_id.encode("utf-8")).hexdigest()
    client = DeerFlowClient(
        checkpointer=InMemorySaver(),
        model_name=args.model,
        thinking_enabled=args.thinking,
        subagent_enabled=False,
        plan_mode=False,
        available_skills=set(),
        environment="incubation-agent-eval",
    )
    configured_models = client.list_models()["models"]
    if not configured_models:
        raise RuntimeError("no DeerFlow model is configured")
    model_id = args.model or str(configured_models[0]["name"])
    tool_surface = _tool_surface(client, model_name=model_id)
    trial_ids = tuple(trial.trial_id for trial in trials)
    preflight_ledger = PreflightLedger(args.output_root)
    trace_ledger = AgentTraceLedger(args.output_root)
    preflight_ledger.create_run(
        run_id=run_id,
        model_id=model_id,
        trial_ids=trial_ids,
        system_prompt_sha256=sha256(SYSTEM_PROMPT_TEMPLATE.encode("utf-8")).hexdigest(),
        corpus_sha256=corpus_sha256,
        created_at=created_at,
    )
    trace_ledger.create_run(
        run_id=run_id,
        trial_ids=trial_ids,
        actor_sha256=actor_sha256,
        tool_surface=tool_surface,
        created_at=created_at,
    )

    run_dir = args.output_root / run_id
    database_path = run_dir / "agent-state.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def setup_state() -> None:
        await bootstrap_incubation_schema(engine)
        repository = IncubationRepository(session_factory)
        for trial in trials:
            await seed_trial_state(
                repository=repository,
                trial=trial,
                owner_id=actor_id,
                corpus_sha256=corpus_sha256,
                created_at=created_at,
            )

    asyncio.run(setup_state())
    try:
        with _bind_evaluation_session_factory(session_factory):
            for trial in trials:
                prompt = build_agent_eval_prompt(trial)
                thread_id = f"incubation-{_safe_component(run_id)}-{_safe_component(trial.trial_id)}"
                collector = AgentEventCollector()
                started_at = datetime.now(UTC)
                terminal_error_code: str | None = None
                try:
                    for event in client.stream(
                        prompt,
                        thread_id=thread_id,
                        user_id=actor_id,
                        recursion_limit=args.max_agent_steps,
                    ):
                        collector.consume(event)
                except Exception as error:
                    terminal_error_code = _error_code(error)
                observation = collector.finish()
                if terminal_error_code is None:
                    terminal_error_code = observation.fallback_error_code
                if terminal_error_code is None and not observation.output:
                    terminal_error_code = "empty_model_output"
                completed_at = datetime.now(UTC)
                trace_ledger.record_trace(
                    run_id=run_id,
                    trace=AgentTrialTrace(
                        trial_id=trial.trial_id,
                        thread_id=thread_id,
                        project_id=trial.project_id,
                        actor_sha256=actor_sha256,
                        events=observation.events,
                        final_message_id=observation.final_message_id,
                        usage=observation.usage,
                        terminal_error_code=terminal_error_code,
                    ),
                )
                if terminal_error_code is None:
                    preflight_ledger.record_success(
                        run_id=run_id,
                        trial_id=trial.trial_id,
                        prompt=prompt,
                        output=observation.output,
                        started_at=started_at,
                        completed_at=completed_at,
                        usage=observation.usage,
                    )
                    print(f"{trial.trial_id}: succeeded")
                else:
                    preflight_ledger.record_failure(
                        run_id=run_id,
                        trial_id=trial.trial_id,
                        prompt=prompt,
                        error_code=terminal_error_code,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                    print(f"{trial.trial_id}: failed ({terminal_error_code})")
    finally:
        asyncio.run(engine.dispose())
        _write_database_digest(database_path)

    completion = preflight_ledger.complete_run(
        run_id,
        completed_at=datetime.now(UTC),
    )
    preflight_ledger.verify_run(run_id)
    trace_verification = trace_ledger.verify_run(run_id)
    if not trace_verification.complete:
        raise RuntimeError("agent evaluation trace ledger is incomplete")
    print(f"run={run_id} status={completion.status} succeeded={completion.succeeded} failed={completion.failed}")
    print(f"evidence={run_dir}")
    return 0 if completion.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
