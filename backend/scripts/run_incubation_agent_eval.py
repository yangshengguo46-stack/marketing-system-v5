"""Run capped incubation evaluations through DeerFlow's real Lead Agent and tools."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import re
import threading
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, override

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage
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
from deerflow.config.app_config import AppConfig, get_app_config
from deerflow.config.subagents_config import CustomSubagentConfig, SubagentOverrideConfig
from deerflow.config.token_budget_config import TokenBudgetConfig

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
_MIN_AGENT_GRAPH_STEPS = 40
_MAX_AGENT_GRAPH_STEPS = 100
_MAX_EVALUATION_MODEL_CALLS = 12
_MIN_SUBAGENT_GRAPH_STEPS = 40
_MAX_SUBAGENT_GRAPH_STEPS = 80
_MIN_SUBAGENT_TOKENS = 1_000
_MAX_SUBAGENT_TOKENS = 100_000
_SUBAGENT_MODES = ("disabled", "evidence-review")
INCUBATION_EVIDENCE_RESEARCHER_NAME = "incubation-evidence-researcher"
_EVIDENCE_RESEARCHER_TIMEOUT_SECONDS = 120
_EVIDENCE_RESEARCHER_DESCRIPTION = "Use only when an incubation judgment needs a bounded, read-only reconciliation of project truths, source evidence, and reviewed methods; returns an evidence brief, never a final strategy."
_EVIDENCE_RESEARCHER_SYSTEM_PROMPT = """你是总控 Lead Agent 的只读孵化证据研究员，不是面向用户的第二个孵化顾问。

你的职责是检查被委派项目的事实、外部证据和已复核方法，为 Lead 提供一份有界证据简报。最终孵化判断、与用户沟通、项目状态修改和不可逆操作都只属于 Lead Agent。

权限边界：
- 只能读取委派范围内的项目事实、项目证据和方法上下文；不得修改、创建或批准任何业务状态。
- 不得向用户提问，不得再次委派，不得发布内容，不得操作浏览器、桌面、文件或外部账号。
- 不得把常见做法、主体标签、方法卡、平台项目说明或相似案例写成当前项目已证实的结论。
- 不得补造身份、表现力、资产、案例、效果、渠道、产能、价格、预算、频率或指标阈值。
- 可以提出条件化选项，但不能替 Lead 选择定位、表现形式、内容路线、平台或变现方案。

返回一份简洁证据简报，固定包含以下五个标题；允许某一项为空，但不能填造内容：
1. 支持事实与证据：逐项写明事实或观察以及可用引用。
2. 会反转判断的未知：只列会真正改变路线的最少主体信息。
3. 条件化选项：写清每个选项成立所需条件，不作最终推荐。
4. 无依据假设：指出 Lead 应避免沿用或新增的具体假设。
5. 冲突与局限：记录证据冲突、过期、适用范围和仍不可判断之处。

只返回这份研究简报，不写最终孵化判断。"""


def build_agent_eval_app_config(
    host_config: AppConfig,
    *,
    subagent_mode: str = "disabled",
    max_subagent_steps: int | None = None,
    max_subagent_tokens: int | None = None,
) -> AppConfig:
    """Copy host configuration and isolate the selected evaluation architecture."""

    evaluation_memory = host_config.memory.model_copy(
        update={
            "enabled": False,
            "injection_enabled": False,
        }
    )
    if subagent_mode not in _SUBAGENT_MODES:
        raise ValueError(f"unknown subagent mode: {subagent_mode}")
    if subagent_mode == "disabled":
        if max_subagent_steps is not None or max_subagent_tokens is not None:
            raise ValueError("subagent caps require an enabled subagent mode")
        return host_config.model_copy(update={"memory": evaluation_memory})
    if max_subagent_steps is None or max_subagent_tokens is None:
        raise ValueError("evidence-review mode requires explicit subagent step and token caps")
    if not _MIN_SUBAGENT_GRAPH_STEPS <= max_subagent_steps <= _MAX_SUBAGENT_GRAPH_STEPS:
        raise ValueError("subagent step cap is outside the evaluation range")
    if not _MIN_SUBAGENT_TOKENS <= max_subagent_tokens <= _MAX_SUBAGENT_TOKENS:
        raise ValueError("subagent token cap is outside the evaluation range")

    specialist = CustomSubagentConfig(
        description=_EVIDENCE_RESEARCHER_DESCRIPTION,
        system_prompt=_EVIDENCE_RESEARCHER_SYSTEM_PROMPT,
        tools=sorted(_REQUIRED_INCUBATION_TOOLS),
        disallowed_tools=["task", "ask_clarification", "present_files"],
        skills=[],
        model="inherit",
        max_turns=max_subagent_steps,
        timeout_seconds=_EVIDENCE_RESEARCHER_TIMEOUT_SECONDS,
    )
    specialist_override = SubagentOverrideConfig(
        token_budget=TokenBudgetConfig(
            enabled=True,
            max_tokens=max_subagent_tokens,
            warn_threshold=0.7,
            hard_stop_threshold=1.0,
        )
    )
    evaluation_subagents = host_config.subagents.model_copy(
        update={
            "allowed_agents": [INCUBATION_EVIDENCE_RESEARCHER_NAME],
            "max_total_per_run": 1,
            "agents": {INCUBATION_EVIDENCE_RESEARCHER_NAME: specialist_override},
            "custom_agents": {INCUBATION_EVIDENCE_RESEARCHER_NAME: specialist},
        }
    )
    return host_config.model_copy(
        update={
            "memory": evaluation_memory,
            "subagents": evaluation_subagents,
        }
    )


class EvaluationModelCallBudget(AgentMiddleware):
    """Hard per-run model-call cap used only by the paid evaluation CLI."""

    def __init__(self, *, max_calls: int) -> None:
        super().__init__()
        self.max_calls = max_calls
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, str], int] = {}

    def reserve(self, key: tuple[str, str]) -> bool:
        with self._lock:
            count = self._counts.get(key, 0)
            if count >= self.max_calls:
                return False
            self._counts[key] = count + 1
            return True

    @staticmethod
    def _key(request: ModelRequest) -> tuple[str, str]:
        context = getattr(request.runtime, "context", None)
        if isinstance(context, Mapping):
            return (
                str(context.get("thread_id") or "unknown-thread"),
                str(context.get("run_id") or "unknown-run"),
            )
        return "unknown-thread", str(id(request.runtime))

    def _fallback(self) -> ModelResponse:
        return ModelResponse(
            result=[
                AIMessage(
                    content="Evaluation stopped after reaching its model-call budget.",
                    additional_kwargs={
                        "deerflow_error_fallback": True,
                        "error_reason": "evaluation_model_call_cap_reached",
                    },
                )
            ]
        )

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        if not self.reserve(self._key(request)):
            return self._fallback()
        return handler(request)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        if not self.reserve(self._key(request)):
            return self._fallback()
        return await handler(request)


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
            project_id=f"agent-eval-{run_component}-{_safe_component(case.case_id)}",
            case=case,
            include_mutation=mutation,
        )
        for case in cases
        for mutation in phases
    )
    if len({trial.trial_id for trial in trials}) != len(trials):
        raise ValueError("agent evaluation trial ids must be unique")
    if any(len(trial.project_id) > 255 for trial in trials):
        raise ValueError("agent evaluation project id exceeds storage limit")
    return trials


def build_agent_eval_prompt(trial: AgentEvalTrialSpec) -> str:
    sections = [
        "请处理系统中已经存在的 MCN 孵化项目。",
        f"项目 ID：{trial.project_id}",
        "请从系统保存的项目资料开始处理起号、表现形式、持续内容、变现与转化问题，不要为了本轮看起来完整而假定主体信息。",
        "区分已知事实、外部证据、暂定选择、关键未知和替代方案；信息不足时先说明目前能确定什么，指出会改变结论的最少主体信息，并只给条件化备选或最小试验，不要无依据宣布一种表现形式最适合。资料足够时才给完整路线，且不得补造身份、资产、效果、客户、渠道、产能、价格、预算或指标阈值。",
        "本次评测请直接在对话中给出简洁判断，不要创建或呈现文件。",
    ]
    if trial.include_mutation:
        sections.append("这是同一项目的新增证据轮次；请结合上一轮实际回答与当前项目账本，指出哪些判断应当改变、保留或继续未知，不得虚构上一轮观点。")
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
    return tuple(statements)


async def seed_trial_state(
    *,
    repository: IncubationRepository,
    trial: AgentEvalTrialSpec,
    owner_id: str,
    corpus_sha256: str,
    created_at: datetime,
) -> None:
    if trial.include_mutation:
        raise ValueError("seed_trial_state requires the initial trial")
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


async def append_trial_mutation(
    *,
    repository: IncubationRepository,
    trial: AgentEvalTrialSpec,
    owner_id: str,
    corpus_sha256: str,
    created_at: datetime,
) -> None:
    """Append new evidence to the existing project before its next turn."""

    if not trial.include_mutation:
        raise ValueError("append_trial_mutation requires the mutation trial")
    statement = f"新补充证据：{trial.case.mutation}"
    evidence_id = f"{trial.project_id}-mutation-evidence"
    source_payload = {
        "case_id": trial.case.case_id,
        "phase": "mutation",
        "statement": statement,
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
    await repository.append_evidence(
        EvidenceItem(
            evidence_id=evidence_id,
            owner_id=owner_id,
            project_id=trial.project_id,
            kind=EvidenceKind.USER_ARTIFACT,
            status=EvidenceStatus.ACTIVE,
            source_locator=(f"eval-corpus://incubation-eval-cases/{trial.case.case_id}#mutation"),
            captured_at=created_at,
            content_hash=content_hash,
            observed_facts=(statement,),
            limitations=("这是版本化评测新增输入，不是账号实际经营结果，也不能证明某条孵化路线有效。",),
            artifact_refs=(f"corpus-sha256:{corpus_sha256}",),
            source_updated_label=f"corpus-sha256:{corpus_sha256}",
        ),
        operation_key=f"{trial.project_id}-append-mutation-evidence",
    )
    await repository.append_truth(
        ProjectTruth(
            truth_id=f"{trial.project_id}-mutation",
            owner_id=owner_id,
            project_id=trial.project_id,
            kind=TruthKind.SOURCE_FACT,
            statement=statement,
            created_at=created_at,
            source_ref=evidence_id,
            evidence_refs=(evidence_id,),
        ),
        operation_key=f"{trial.project_id}-append-mutation-truth",
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


def _tool_surface(
    client: DeerFlowClient,
    *,
    model_name: str,
    subagent_enabled: bool,
) -> list[dict[str, Any]]:
    tools = client._get_tools(
        model_name=model_name,
        subagent_enabled=subagent_enabled,
    )
    schemas_by_name = {tool.name: convert_to_openai_tool(tool) for tool in tools}
    required_tools = set(_REQUIRED_INCUBATION_TOOLS)
    if subagent_enabled:
        required_tools.add("task")
    missing = required_tools - schemas_by_name.keys()
    if missing:
        raise RuntimeError(f"required incubation tools are missing: {sorted(missing)}")
    return [schemas_by_name[name] for name in sorted(schemas_by_name)]


def _evaluation_system_contract_sha256(
    *,
    app_config: AppConfig,
    subagent_mode: str,
) -> str:
    if subagent_mode == "disabled":
        return sha256(SYSTEM_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
    specialist = app_config.subagents.custom_agents[INCUBATION_EVIDENCE_RESEARCHER_NAME]
    contract = {
        "lead_system_prompt_template": SYSTEM_PROMPT_TEMPLATE,
        "subagent_mode": subagent_mode,
        "allowed_agents": app_config.subagents.allowed_agents,
        "max_total_per_run": app_config.subagents.max_total_per_run,
        "specialist": specialist.model_dump(mode="json"),
        "specialist_override": app_config.subagents.agents[INCUBATION_EVIDENCE_RESEARCHER_NAME].model_dump(mode="json"),
    }
    encoded = json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _write_experiment_manifest(
    *,
    run_dir: Path,
    subagent_mode: str,
    app_config: AppConfig,
    max_agent_steps: int,
    max_model_calls: int,
    max_subagent_steps: int | None,
    max_subagent_tokens: int | None,
    created_at: datetime,
) -> None:
    subagent_enabled = subagent_mode != "disabled"
    payload = {
        "schema_version": "mcn-incubation-agent-eval-experiment-v1",
        "subagent_mode": subagent_mode,
        "decision_authority": "lead-agent",
        "allowed_subagents": (list(app_config.subagents.allowed_agents or []) if subagent_enabled else []),
        "max_total_delegations": (app_config.subagents.max_total_per_run if subagent_enabled else 0),
        "max_agent_steps": max_agent_steps,
        "max_lead_model_calls": max_model_calls,
        "max_subagent_steps": max_subagent_steps,
        "max_subagent_tokens": max_subagent_tokens,
        "system_contract_sha256": _evaluation_system_contract_sha256(
            app_config=app_config,
            subagent_mode=subagent_mode,
        ),
        "created_at": created_at.isoformat(),
    }
    text = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    manifest_path = run_dir / "experiment.json"
    digest_path = run_dir / "experiment.json.sha256"
    try:
        with manifest_path.open("x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if manifest_path.read_text(encoding="utf-8") != text:
            raise RuntimeError("agent evaluation experiment manifest already differs") from None
    digest_text = sha256(text.encode("utf-8")).hexdigest() + "\n"
    try:
        with digest_path.open("x", encoding="utf-8") as handle:
            handle.write(digest_text)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if digest_path.read_text(encoding="utf-8") != digest_text:
            raise RuntimeError("agent evaluation experiment digest already differs") from None


def _verify_experiment_manifest(run_dir: Path) -> None:
    manifest_path = run_dir / "experiment.json"
    digest_path = run_dir / "experiment.json.sha256"
    expected = digest_path.read_text(encoding="utf-8").strip()
    actual = sha256(manifest_path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError("agent evaluation experiment manifest hash mismatch")


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
        help="Append each case's new evidence before a second turn on the same project and thread",
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
        help=(f"LangGraph super-step limit per trial; the current Lead Agent graph requires at least {_MIN_AGENT_GRAPH_STEPS} for framework overhead"),
    )
    parser.add_argument(
        "--max-model-calls",
        type=int,
        required=True,
        help="Hard Lead Agent model-call cap per trial for evaluation cost control",
    )
    parser.add_argument(
        "--subagent-mode",
        choices=_SUBAGENT_MODES,
        default="disabled",
        help="Evaluation architecture variant; evidence-review enables one read-only specialist",
    )
    parser.add_argument(
        "--max-subagent-steps",
        type=int,
        help="Required graph-step cap for the enabled evidence specialist",
    )
    parser.add_argument(
        "--max-subagent-tokens",
        type=int,
        help="Required total-token backstop for the enabled evidence specialist",
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
    if not _MIN_AGENT_GRAPH_STEPS <= args.max_agent_steps <= _MAX_AGENT_GRAPH_STEPS:
        parser.error(f"--max-agent-steps must be between {_MIN_AGENT_GRAPH_STEPS} and {_MAX_AGENT_GRAPH_STEPS}")
    if not 1 <= args.max_model_calls <= _MAX_EVALUATION_MODEL_CALLS:
        parser.error(f"--max-model-calls must be between 1 and {_MAX_EVALUATION_MODEL_CALLS}")
    if args.subagent_mode == "disabled":
        if args.max_subagent_steps is not None or args.max_subagent_tokens is not None:
            parser.error("subagent caps can only be used with an enabled --subagent-mode")
    else:
        if args.max_subagent_steps is None or args.max_subagent_tokens is None:
            parser.error("evidence-review requires --max-subagent-steps and --max-subagent-tokens")
        if not _MIN_SUBAGENT_GRAPH_STEPS <= args.max_subagent_steps <= _MAX_SUBAGENT_GRAPH_STEPS:
            parser.error(f"--max-subagent-steps must be between {_MIN_SUBAGENT_GRAPH_STEPS} and {_MAX_SUBAGENT_GRAPH_STEPS}")
        if not _MIN_SUBAGENT_TOKENS <= args.max_subagent_tokens <= _MAX_SUBAGENT_TOKENS:
            parser.error(f"--max-subagent-tokens must be between {_MIN_SUBAGENT_TOKENS} and {_MAX_SUBAGENT_TOKENS}")
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
    subagent_enabled = args.subagent_mode != "disabled"
    evaluation_app_config = build_agent_eval_app_config(
        get_app_config(),
        subagent_mode=args.subagent_mode,
        max_subagent_steps=args.max_subagent_steps,
        max_subagent_tokens=args.max_subagent_tokens,
    )
    client = DeerFlowClient(
        checkpointer=InMemorySaver(),
        model_name=args.model,
        thinking_enabled=args.thinking,
        subagent_enabled=subagent_enabled,
        plan_mode=False,
        available_skills=set(),
        middlewares=[EvaluationModelCallBudget(max_calls=args.max_model_calls)],
        environment="incubation-agent-eval",
        app_config=evaluation_app_config,
    )
    configured_models = client.list_models()["models"]
    if not configured_models:
        raise RuntimeError("no DeerFlow model is configured")
    model_id = args.model or str(configured_models[0]["name"])
    tool_surface = _tool_surface(
        client,
        model_name=model_id,
        subagent_enabled=subagent_enabled,
    )
    trial_ids = tuple(trial.trial_id for trial in trials)
    preflight_ledger = PreflightLedger(args.output_root)
    trace_ledger = AgentTraceLedger(args.output_root)
    preflight_ledger.create_run(
        run_id=run_id,
        model_id=model_id,
        trial_ids=trial_ids,
        system_prompt_sha256=_evaluation_system_contract_sha256(
            app_config=evaluation_app_config,
            subagent_mode=args.subagent_mode,
        ),
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
    _write_experiment_manifest(
        run_dir=run_dir,
        subagent_mode=args.subagent_mode,
        app_config=evaluation_app_config,
        max_agent_steps=args.max_agent_steps,
        max_model_calls=args.max_model_calls,
        max_subagent_steps=args.max_subagent_steps,
        max_subagent_tokens=args.max_subagent_tokens,
        created_at=created_at,
    )
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
            if trial.include_mutation:
                continue
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
                if trial.include_mutation:
                    asyncio.run(
                        append_trial_mutation(
                            repository=IncubationRepository(session_factory),
                            trial=trial,
                            owner_id=actor_id,
                            corpus_sha256=corpus_sha256,
                            created_at=datetime.now(UTC),
                        )
                    )
                prompt = build_agent_eval_prompt(trial)
                thread_id = f"incubation-{_safe_component(run_id)}-{_safe_component(trial.case.case_id)}"
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
    _verify_experiment_manifest(run_dir)
    print(f"run={run_id} status={completion.status} succeeded={completion.succeeded} failed={completion.failed}")
    print(f"evidence={run_dir}")
    return 0 if completion.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
