"""Run capped incubation evaluations through DeerFlow's real Lead Agent and tools."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import re
import threading
from collections import Counter
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any, override

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
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
from mcn_incubation.marketing_reasoning_evaluation import (
    SHARED_MARKETING_REASONING_CONTRACT,
)
from mcn_incubation.persistence import IncubationRepository
from mcn_incubation.persistence_schema import bootstrap_incubation_schema
from mcn_incubation.preflight import PreflightLedger
from mcn_incubation.user_reasoning_evaluation import distilled_user_reasoning_context
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from deerflow.agents.lead_agent.prompt import SYSTEM_PROMPT_TEMPLATE
from deerflow.client import DeerFlowClient
from deerflow.config.app_config import AppConfig, get_app_config
from deerflow.config.subagents_config import CustomSubagentConfig, SubagentOverrideConfig
from deerflow.config.token_budget_config import TokenBudgetConfig
from deerflow.utils.thread_id import validate_thread_id

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "incubation-eval-cases.jsonl"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / ".deer-flow" / "incubation-agent-eval"
_REQUIRED_INCUBATION_READ_TOOLS = frozenset(
    {
        "incubation_context",
        "incubation_project_context",
        "incubation_project_evidence",
    }
)
_REQUIRED_INCUBATION_LEAD_TOOLS = frozenset(
    {
        *_REQUIRED_INCUBATION_READ_TOOLS,
        "incubation_record_subject_answer",
    }
)
_MIN_AGENT_GRAPH_STEPS = 40
_MAX_AGENT_GRAPH_STEPS = 100
_MAX_EVALUATION_MODEL_CALLS = 12
_MIN_SUBAGENT_GRAPH_STEPS = 40
_MAX_SUBAGENT_GRAPH_STEPS = 80
_MIN_SUBAGENT_TOKENS = 1_000
_MAX_SUBAGENT_TOKENS = 100_000
_SUBAGENT_MODES = (
    "disabled",
    "evidence-review",
    "incubation-team",
    "marketing-reasoning-team",
)
_TEAM_SUBAGENT_MODES = frozenset({"incubation-team", "marketing-reasoning-team"})
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

INCUBATION_TEAM_SPECIALIST_NAMES = (
    "incubation-positioning-specialist",
    "incubation-audience-specialist",
    "incubation-content-specialist",
    "incubation-expression-specialist",
    "incubation-commercial-specialist",
)
_INCUBATION_TEAM_TIMEOUT_SECONDS = 120
_INCUBATION_TEAM_MAX_CONCURRENT = 3
_INCUBATION_TEAM_READ_TOOLS = (
    "incubation_project_context",
    "incubation_project_evidence",
)
_INCUBATION_TEAM_ROLE_CONTRACTS: dict[str, tuple[str, str]] = {
    "incubation-positioning-specialist": (
        "负责 IP 主体、赛道、人设、业务对象与账号价值承诺的定位板块；识别商品名、品类和用户真正关心的问题是否处于不同语义层，不替其他板块拍板。",
        "定位板块判断：给出当前最值得保留的一至三个定位假设，说明每个假设中的 IP 主体、赛道、人设、记忆点和业务回路，并指出什么证据会使它失效。",
    ),
    "incubation-audience-specialist": (
        "负责粉丝与购买者的受众板块；严格区分目标受众假设、实际受众证据、使用或决策情境以及仍未知的信息，不用人口标签代替动机。",
        "受众板块判断：描述受众在什么情境下遇到什么问题、为什么愿意看和为什么可能行动；明确标注受众假设与实际受众证据，避免刻板推断。",
    ),
    "incubation-content-specialist": (
        "负责可持续内容世界与内容发动机；研究母题、栏目、事件、人物、冲突和可展开的内容素材，但不选择镜头前的表现形式。",
        "内容板块判断：提出可持续的内容世界、母题和系列发动机。真实案例、历史故事、现实事件、神话或未来想象都属于内容候选，不得把它们写成表现形式。",
    ),
    "incubation-expression-specialist": (
        "负责内容如何被呈现的表现形式板块；比较口播、对话、采访、微短剧、情景剧、纪录跟拍、演示、纯素材视频和图文等形式，并服从已知表现力、资源、隐私和产能。",
        "表现形式板块判断：给出条件化形式组合和最小验证办法。口播不得作为默认答案；历史故事不是表现形式，历史故事可以分别用口播、情景剧、动画、纯素材或图文来表达。",
    ),
    "incubation-commercial-specialist": (
        "负责变现、转化和履约板块；检查内容如何形成信任、触发行动、承接线索或成交，并让商业路线与真实产品、服务和交付能力相连。",
        "商业板块判断：提出可验证的变现路径和内容到信任、行动、成交、复购的连接；不得补造价格、渠道、客户、预算、转化率或履约能力。",
    ),
}

MARKETING_REASONING_TEAM_SPECIALIST_NAMES = (
    "semantic-center-specialist",
    "human-demand-specialist",
    "content-world-specialist",
    "expression-form-specialist",
    "commercial-attribution-specialist",
)
_MARKETING_REASONING_TEAM_ROLE_CONTRACTS: dict[str, tuple[str, str]] = {
    "semantic-center-specialist": (
        "负责辨认商业对象的语义中心，不让材质、修饰词或表面商品名自动吞掉真正的品类中心、用途与账号主语。",
        "语义中心板块：比较至少两个合理主语候选，拆清品类中心、材质或修饰、功能、用途与动作，并说明选择哪个候选会怎样改变后续完整因果链。",
    ),
    "human-demand-specialist": (
        "负责从用途与动作推演社会行为、人类需求和关系张力，同时审查跨越是否过度、刻板或已经失去商业联系。",
        "人类需求板块：提出动作到社会行为、人类需求的候选连接，逐条解释中间因果、最强反例和应退回的跨越；标签不能代替动机。",
    ),
    "content-world-specialist": (
        "负责把候选长期母题展开为可持续内容世界，检查容量、差异和回到商业对象的语义桥，不选择镜头前的表现形式。",
        "内容世界板块：围绕候选母题展开人物、事件、关系、冲突、时间与空间中的内容世界；内容来源不是表现形式，并指出哪些分支虽有流量想象却没有自然归因。",
    ),
    "expression-form-specialist": (
        "负责比较内容如何呈现，只能依据已知主体条件，或明确写成待验证的条件化形式候选。",
        "表现形式板块：把候选内容分别映射到口播、对话、情景、纪录、演示、纯素材或图文等表达；未知主体条件不得被补造，常见形式和低成本不等于适合。",
    ),
    "commercial-attribution-specialist": (
        "负责检验内容、信任、需求心智、行动与真实产品或服务之间是否形成自然商业归因，而不是在内容末尾硬贴商品。",
        "商业归因板块：审查不卖而卖的回路，说明用户为何会把该母题的理解归因给经营主体、何种真实需求会触发行动，以及哪里可能只有泛流量没有转化。",
    ),
}


def _team_specialist_names(subagent_mode: str) -> tuple[str, ...]:
    if subagent_mode == "incubation-team":
        return INCUBATION_TEAM_SPECIALIST_NAMES
    if subagent_mode == "marketing-reasoning-team":
        return MARKETING_REASONING_TEAM_SPECIALIST_NAMES
    raise ValueError(f"subagent mode is not a team: {subagent_mode}")


def _incubation_team_system_prompt(name: str) -> str:
    role_summary, board_contract = _INCUBATION_TEAM_ROLE_CONTRACTS[name]
    return f"""你是总控 Lead Agent 的 MCN 孵化专业子 Agent，{role_summary}

你不直接面向用户，也不是第二个总控。你对自己的专业板块提出有判断力的方案、备选和反证；跨板块冲突与最终整合只属于 Lead Agent。

共同边界：
- 先读取委派项目的事实账本和证据，再区分已知事实、外部观察、专业推断、创意假设与未知事项。
- 信息不完整也要继续完成有条件的板块判断，不得把缺失信息变成流程硬门或固定问卷。
- 不得补造主体身份、表现力、资源、资产、案例、效果、客户、渠道、产能、价格、预算、频率或指标阈值。
- 不得修改项目状态，不得向用户提问，不得再次委派，不得投票、打分或替 Lead 输出完整孵化方案。
- 不用角色共识冒充市场证据；必须主动寻找最强反证，并指出与相邻板块的依赖或冲突。

{board_contract}

只返回一份有界板块简报，包含：板块判断、依据与事实边界、备选方案、最强反证、关键未知、跨板块依赖或冲突。不要写面向用户的最终整合答案。"""


def _marketing_reasoning_team_system_prompt(name: str) -> str:
    role_summary, board_contract = _MARKETING_REASONING_TEAM_ROLE_CONTRACTS[name]
    return f"""你是总控 Lead Agent 的营销推理专业子 Agent，{role_summary}

你不直接面向用户，也不是第二个总控。所有专家共享下面同一套完整因果链；你必须理解全链后再深化自己的板块，不得只看自己负责的一个节点。

{SHARED_MARKETING_REASONING_CONTRACT}

共同边界：
- 先读取委派项目的事实账本和证据，再区分已知事实、外部观察、专业推断、创意假设与未知事项。
- 信息不完整也要给条件化判断，不得把缺失信息变成固定问卷、阶段或继续工作的硬门。
- 不得修改项目状态，不得向用户提问，不得再次委派，不得投票、打分或替 Lead 输出完整方案。
- 不能用角色共识冒充市场证据；必须主动寻找最强反证，并说明本板块如何改变完整因果链的其他节点。

{board_contract}

只返回一份有界专业简报，包含：核心候选、因果依据、最强反证、替代解释、关键未知、对完整链条的影响。不要复写共同骨架，不要写面向用户的最终答案。"""


class AgentEvalTaskMode(StrEnum):
    FULL_INCUBATION = "full_incubation"
    CONTENT_WORLD = "content_world"


class MethodContextMode(StrEnum):
    AVAILABLE = "available"
    DISABLED = "disabled"
    DISTILLED_USER_REASONING = "distilled_user_reasoning"


class ReasoningContractMode(StrEnum):
    BASELINE = "baseline"
    SHARED_MARKETING_CHAIN = "shared_marketing_chain"


@tool("incubation_context", parse_docstring=True)
def distilled_user_incubation_context(query: str, limit: int = 1) -> dict[str, object]:
    """Retrieve the evaluation-only distilled content-world reasoning card.

    This candidate is advisory and supplies optional reasoning lenses, not case
    answers, a fixed workflow, project facts, or a final incubation judgment.

    Args:
        query: Current content-world question for an unfamiliar business object.
        limit: Compatibility bound from 1 through 10; this candidate returns one card.
    """

    if not query.strip():
        raise ValueError("query cannot be blank")
    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    return distilled_user_reasoning_context()


def build_agent_eval_client(
    *,
    method_context_mode: MethodContextMode,
    **client_kwargs: Any,
) -> DeerFlowClient:
    """Build an evaluation client with an explicitly sealed tool ablation."""

    base_client_type = DeerFlowClient
    if method_context_mode is MethodContextMode.AVAILABLE:
        return base_client_type(**client_kwargs)

    class MethodContextFilteredClient(base_client_type):
        @staticmethod
        def _get_tools(*, model_name: str | None, subagent_enabled: bool):
            tools = base_client_type._get_tools(
                model_name=model_name,
                subagent_enabled=subagent_enabled,
            )
            filtered_tools = [tool for tool in tools if tool.name != "incubation_context"]
            if method_context_mode is MethodContextMode.DISTILLED_USER_REASONING:
                filtered_tools.append(distilled_user_incubation_context)
            return filtered_tools

    return MethodContextFilteredClient(**client_kwargs)


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
        raise ValueError("enabled subagent modes require explicit subagent step and token caps")
    if not _MIN_SUBAGENT_GRAPH_STEPS <= max_subagent_steps <= _MAX_SUBAGENT_GRAPH_STEPS:
        raise ValueError("subagent step cap is outside the evaluation range")
    if not _MIN_SUBAGENT_TOKENS <= max_subagent_tokens <= _MAX_SUBAGENT_TOKENS:
        raise ValueError("subagent token cap is outside the evaluation range")

    denied_tools = [
        "task",
        "ask_clarification",
        "present_files",
        "incubation_record_subject_answer",
    ]

    def specialist_override() -> SubagentOverrideConfig:
        return SubagentOverrideConfig(
            token_budget=TokenBudgetConfig(
                enabled=True,
                max_tokens=max_subagent_tokens,
                warn_threshold=0.7,
                hard_stop_threshold=1.0,
            )
        )

    if subagent_mode == "evidence-review":
        custom_agents = {
            INCUBATION_EVIDENCE_RESEARCHER_NAME: CustomSubagentConfig(
                description=_EVIDENCE_RESEARCHER_DESCRIPTION,
                system_prompt=_EVIDENCE_RESEARCHER_SYSTEM_PROMPT,
                tools=sorted(_REQUIRED_INCUBATION_READ_TOOLS),
                disallowed_tools=denied_tools,
                skills=[],
                model="inherit",
                max_turns=max_subagent_steps,
                timeout_seconds=_EVIDENCE_RESEARCHER_TIMEOUT_SECONDS,
            )
        }
    elif subagent_mode == "incubation-team":
        custom_agents = {
            name: CustomSubagentConfig(
                description=_INCUBATION_TEAM_ROLE_CONTRACTS[name][0],
                system_prompt=_incubation_team_system_prompt(name),
                tools=list(_INCUBATION_TEAM_READ_TOOLS),
                disallowed_tools=denied_tools,
                skills=[],
                model="inherit",
                max_turns=max_subagent_steps,
                timeout_seconds=_INCUBATION_TEAM_TIMEOUT_SECONDS,
            )
            for name in INCUBATION_TEAM_SPECIALIST_NAMES
        }
    else:
        custom_agents = {
            name: CustomSubagentConfig(
                description=_MARKETING_REASONING_TEAM_ROLE_CONTRACTS[name][0],
                system_prompt=_marketing_reasoning_team_system_prompt(name),
                tools=list(_INCUBATION_TEAM_READ_TOOLS),
                disallowed_tools=denied_tools,
                skills=[],
                model="inherit",
                max_turns=max_subagent_steps,
                timeout_seconds=_INCUBATION_TEAM_TIMEOUT_SECONDS,
            )
            for name in MARKETING_REASONING_TEAM_SPECIALIST_NAMES
        }
    allowed_agents = list(custom_agents)
    evaluation_subagents = host_config.subagents.model_copy(
        update={
            "allowed_agents": allowed_agents,
            "max_total_per_run": len(allowed_agents),
            "agents": {name: specialist_override() for name in allowed_agents},
            "custom_agents": custom_agents,
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


def build_trial_thread_id(*, run_id: str, case_id: str) -> str:
    raw = f"incubation-{_safe_component(run_id)}-{_safe_component(case_id)}"
    thread_safe = raw.replace(".", "-")
    if thread_safe == raw and len(thread_safe) <= 64:
        return validate_thread_id(thread_safe)
    digest = sha256(raw.encode("ascii")).hexdigest()[:16]
    prefix = thread_safe[: 64 - len(digest) - 1].rstrip("-_")
    return validate_thread_id(f"{prefix}-{digest}")


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


def build_agent_eval_prompt(
    trial: AgentEvalTrialSpec,
    *,
    task_mode: AgentEvalTaskMode = AgentEvalTaskMode.FULL_INCUBATION,
    subagent_mode: str = "disabled",
    reasoning_contract_mode: ReasoningContractMode = ReasoningContractMode.BASELINE,
) -> str:
    if subagent_mode not in _SUBAGENT_MODES:
        raise ValueError(f"unknown subagent mode: {subagent_mode}")
    if subagent_mode in {"incubation-team", "marketing-reasoning-team"} and task_mode is not AgentEvalTaskMode.FULL_INCUBATION:
        raise ValueError(f"{subagent_mode} evaluation requires full_incubation task mode")
    if subagent_mode == "marketing-reasoning-team" and reasoning_contract_mode is not ReasoningContractMode.SHARED_MARKETING_CHAIN:
        raise ValueError("marketing-reasoning-team requires the shared marketing chain")
    sections = [
        "请处理系统中已经存在的 MCN 孵化项目。",
        f"项目 ID：{trial.project_id}",
    ]
    if task_mode is AgentEvalTaskMode.CONTENT_WORLD:
        sections.extend(
            (
                f"用户原始请求：{trial.case.scenario}",
                "用户本轮只要求先打开这个商业对象的起号思路。请保持当前任务边界，不要扩写成完整孵化交付。",
                "本次评测请直接在对话中回答，不要创建或呈现文件。",
            )
        )
    else:
        sections.extend(
            (
                "请从系统保存的项目资料开始处理起号、表现形式、持续内容、变现与转化问题，不要为了本轮看起来完整而假定主体信息。",
                "区分已知事实、外部证据、暂定选择、关键未知和替代方案；信息不足时先说明目前能确定什么，指出会改变结论的最少主体信息，并只给条件化备选或最小试验，不要无依据宣布一种表现形式最适合。资料足够时才给完整路线，且不得补造身份、资产、效果、客户、渠道、产能、价格、预算或指标阈值。",
                "本次评测请直接在对话中给出简洁判断，不要创建或呈现文件。",
            )
        )
    if reasoning_contract_mode is ReasoningContractMode.SHARED_MARKETING_CHAIN:
        sections.append(
            f"""本轮使用以下共同营销推理骨架。它只约束内部推演，不是给用户看的回答目录：

{SHARED_MARKETING_REASONING_CONTRACT}

请在内部维护一条可修订的完整因果链：商业对象、语义中心、动作与用途、社会行为与长期需求、长期母题、内容世界、表现形式、商业归因、反证与未知。节点可以为空或被推翻，不得为了填满而补造；最终回答不要把内部链条复写成栏目式答案。"""
        )
    if subagent_mode == "incubation-team":
        team_lines = "\n".join(f"- {name}" for name in INCUBATION_TEAM_SPECIALIST_NAMES)
        sections.append(
            f"""本轮是隔离的多 Agent 孵化团队架构评测。请把以下每个专业子 Agent 恰好委派一次：
{team_lines}

这些是同时审视同一项目的专业板块，不是线性阶段，也不存在某一板块完成后才能继续的语义硬门。
请让独立板块尽量并行，每批最多委派三个，角色可以按任意组合分批；分批只是技术并发限制，不代表业务先后。
给每个子 Agent 传入同一项目 ID 和它自己的板块问题，让它读取项目事实与证据后返回板块简报。

内容与表现形式是两个不同板块：历史故事、真实案例、现实事件属于内容候选；口播、情景剧、微短剧、纯素材视频和图文属于表现形式。
收到全部简报后，只有 Lead 可以处理板块冲突并给用户一个统一判断；不得投票、不得打分、不得直接拼接五份简报，也不得把内部一致意见冒充市场证据。"""
        )
    if subagent_mode == "marketing-reasoning-team":
        team_lines = "\n".join(f"- {name}" for name in MARKETING_REASONING_TEAM_SPECIALIST_NAMES)
        sections.append(
            f"""本轮是隔离的共享营销推理团队评测。请把以下每个专业子 Agent 恰好委派一次：
{team_lines}

五个专家都已获得同一套完整因果链，只从不同角度把它推深；这不是线性阶段，也不存在某一节点完成后才能继续的硬门。请让独立问题尽量并行，每批最多三个，分批只表示技术并发限制。
给每个子 Agent 传入同一项目 ID 和它自己的板块问题，让它读取项目事实与证据后返回候选、因果依据、反证、替代解释、未知及对完整链条的影响。

收到全部简报后，由 Lead 总脑收敛为一个统一营销命题和一条自然的内容到生意回路。Lead 必须处理冲突并作出取舍，不得投票、不得打分、不得直接拼接，也不要按五个专家分五节复述内部报告。最终答案仍须保留事实边界、重要备选和会反转判断的未知。"""
        )
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
    method_context_mode: MethodContextMode,
) -> list[dict[str, Any]]:
    tools = client._get_tools(
        model_name=model_name,
        subagent_enabled=subagent_enabled,
    )
    schemas_by_name = {tool.name: convert_to_openai_tool(tool) for tool in tools}
    required_tools = set(_REQUIRED_INCUBATION_LEAD_TOOLS)
    if method_context_mode is MethodContextMode.DISABLED:
        required_tools.remove("incubation_context")
        if "incubation_context" in schemas_by_name:
            raise RuntimeError("method-context ablation did not remove incubation_context")
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
    reasoning_contract_mode: ReasoningContractMode = ReasoningContractMode.BASELINE,
) -> str:
    if subagent_mode == "disabled" and reasoning_contract_mode is ReasoningContractMode.BASELINE:
        return sha256(SYSTEM_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
    allowed_agents = list(app_config.subagents.allowed_agents or [])
    max_concurrent_subagents = _INCUBATION_TEAM_MAX_CONCURRENT if subagent_mode in _TEAM_SUBAGENT_MODES else (1 if allowed_agents else 0)
    contract = {
        "lead_system_prompt_template": SYSTEM_PROMPT_TEMPLATE,
        "reasoning_contract_mode": reasoning_contract_mode.value,
        "shared_marketing_reasoning_contract": (SHARED_MARKETING_REASONING_CONTRACT if reasoning_contract_mode is ReasoningContractMode.SHARED_MARKETING_CHAIN else None),
        "subagent_mode": subagent_mode,
        "allowed_agents": allowed_agents,
        "max_concurrent_subagents": max_concurrent_subagents,
        "max_total_per_run": app_config.subagents.max_total_per_run,
        "specialists": {name: app_config.subagents.custom_agents[name].model_dump(mode="json") for name in allowed_agents},
        "specialist_overrides": {name: app_config.subagents.agents[name].model_dump(mode="json") for name in allowed_agents},
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
    task_mode: AgentEvalTaskMode,
    method_context_mode: MethodContextMode,
    reasoning_contract_mode: ReasoningContractMode,
    created_at: datetime,
) -> None:
    subagent_enabled = subagent_mode != "disabled"
    max_concurrent_subagents = _INCUBATION_TEAM_MAX_CONCURRENT if subagent_mode in _TEAM_SUBAGENT_MODES else (1 if subagent_enabled else 0)
    payload = {
        "schema_version": "mcn-incubation-agent-eval-experiment-v1",
        "subagent_mode": subagent_mode,
        "decision_authority": "lead-agent",
        "allowed_subagents": (list(app_config.subagents.allowed_agents or []) if subagent_enabled else []),
        "max_concurrent_subagents": max_concurrent_subagents,
        "max_total_delegations": (app_config.subagents.max_total_per_run if subagent_enabled else 0),
        "max_agent_steps": max_agent_steps,
        "max_lead_model_calls": max_model_calls,
        "max_subagent_steps": max_subagent_steps,
        "max_subagent_tokens": max_subagent_tokens,
        "task_mode": task_mode.value,
        "method_context_mode": method_context_mode.value,
        "reasoning_contract_mode": reasoning_contract_mode.value,
        "reasoning_contract_sha256": (sha256(SHARED_MARKETING_REASONING_CONTRACT.encode("utf-8")).hexdigest() if reasoning_contract_mode is ReasoningContractMode.SHARED_MARKETING_CHAIN else None),
        "system_contract_sha256": _evaluation_system_contract_sha256(
            app_config=app_config,
            subagent_mode=subagent_mode,
            reasoning_contract_mode=reasoning_contract_mode,
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


def _capture_terminal_task_status(
    task_statuses: dict[str, str],
    event: Any,
) -> None:
    if getattr(event, "type", None) != "custom":
        return
    data = getattr(event, "data", None)
    if not isinstance(data, Mapping):
        return
    status_by_event_type = {
        "task_completed": "completed",
        "task_failed": "failed",
        "task_cancelled": "cancelled",
        "task_timed_out": "timed_out",
    }
    status = status_by_event_type.get(str(data.get("type") or ""))
    task_id = str(data.get("task_id") or "").strip()
    if status is not None and task_id:
        task_statuses[task_id] = status


def _incubation_team_protocol_error(
    events: Sequence[Any],
    *,
    task_statuses: Mapping[str, str],
    project_id: str,
    expected_names: Sequence[str] = INCUBATION_TEAM_SPECIALIST_NAMES,
) -> str | None:
    task_calls = [event for event in events if getattr(event, "event_type", None) == "tool_call" and getattr(event, "tool_name", None) == "task"]
    called_names = []
    for event in task_calls:
        arguments = getattr(event, "arguments", None)
        name = arguments.get("subagent_type") if isinstance(arguments, Mapping) else None
        called_names.append(str(name or ""))

    expected = set(expected_names)
    if any(name not in expected for name in called_names):
        return "incubation_team_unknown_specialist"
    counts = Counter(called_names)
    if any(count > 1 for count in counts.values()):
        return "incubation_team_duplicate_specialist"
    if set(called_names) != expected:
        return "incubation_team_missing_specialist"

    call_ids: set[str] = set()
    for event in task_calls:
        call_id = str(getattr(event, "tool_call_id", None) or "").strip()
        arguments = getattr(event, "arguments", None)
        prompt = arguments.get("prompt") if isinstance(arguments, Mapping) else None
        if not isinstance(prompt, str) or project_id not in prompt:
            return "incubation_team_unbound_project"
        if not call_id:
            return "incubation_team_missing_task_result"
        call_ids.add(call_id)

    result_ids = {str(getattr(event, "tool_call_id", None) or "").strip() for event in events if getattr(event, "event_type", None) == "tool_result" and getattr(event, "tool_name", None) == "task"}
    if not call_ids.issubset(result_ids):
        return "incubation_team_missing_task_result"
    if any(task_statuses.get(call_id) != "completed" for call_id in call_ids):
        return "incubation_team_task_not_completed"
    return None


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
        help="Evaluation architecture variant; enables one evidence reviewer or one of the sealed five-specialist teams",
    )
    parser.add_argument(
        "--task-mode",
        choices=tuple(mode.value for mode in AgentEvalTaskMode),
        default=AgentEvalTaskMode.FULL_INCUBATION.value,
        help="User-task boundary to seal in the evaluation prompt",
    )
    parser.add_argument(
        "--method-context-mode",
        choices=tuple(mode.value for mode in MethodContextMode),
        default=MethodContextMode.AVAILABLE.value,
        help=("Evaluation-only incubation_context variant; disabled removes it and distilled_user_reasoning substitutes one compact candidate card"),
    )
    parser.add_argument(
        "--reasoning-contract-mode",
        choices=tuple(mode.value for mode in ReasoningContractMode),
        default=ReasoningContractMode.BASELINE.value,
        help="Evaluation-only Lead reasoning contract; shared_marketing_chain is case-free and may be matched across single-Lead and team trials",
    )
    parser.add_argument(
        "--max-subagent-steps",
        type=int,
        help="Required per-specialist graph-step cap for an enabled subagent mode",
    )
    parser.add_argument(
        "--max-subagent-tokens",
        type=int,
        help="Required per-specialist total-token backstop for an enabled subagent mode",
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
    reasoning_mode = ReasoningContractMode(args.reasoning_contract_mode)
    method_mode = MethodContextMode(args.method_context_mode)
    if method_mode is MethodContextMode.DISTILLED_USER_REASONING:
        if args.task_mode != AgentEvalTaskMode.CONTENT_WORLD.value or args.subagent_mode != "disabled":
            parser.error("distilled_user_reasoning is only valid for a single-Lead content_world trial")
    if method_mode is MethodContextMode.DISABLED:
        legacy_ablation = args.task_mode == AgentEvalTaskMode.CONTENT_WORLD.value and args.subagent_mode == "disabled"
        shared_chain_trial = reasoning_mode is ReasoningContractMode.SHARED_MARKETING_CHAIN and args.task_mode == AgentEvalTaskMode.FULL_INCUBATION.value and args.subagent_mode in {"disabled", "marketing-reasoning-team"}
        if not (legacy_ablation or shared_chain_trial):
            parser.error("disabled method context is only valid for the sealed content-world ablation or shared-chain comparison")
    if args.subagent_mode in _TEAM_SUBAGENT_MODES and args.task_mode != AgentEvalTaskMode.FULL_INCUBATION.value:
        parser.error(f"{args.subagent_mode} is only valid with --task-mode full_incubation")
    if args.subagent_mode == "marketing-reasoning-team" and reasoning_mode is not ReasoningContractMode.SHARED_MARKETING_CHAIN:
        parser.error("marketing-reasoning-team requires --reasoning-contract-mode shared_marketing_chain")
    if args.subagent_mode == "incubation-team" and reasoning_mode is not ReasoningContractMode.BASELINE:
        parser.error("incubation-team is the immutable A50 baseline and cannot carry the new reasoning contract")
    if args.subagent_mode == "disabled":
        if args.max_subagent_steps is not None or args.max_subagent_tokens is not None:
            parser.error("subagent caps can only be used with an enabled --subagent-mode")
    else:
        if args.max_subagent_steps is None or args.max_subagent_tokens is None:
            parser.error("enabled subagent modes require --max-subagent-steps and --max-subagent-tokens")
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
    task_mode = AgentEvalTaskMode(args.task_mode)
    method_context_mode = MethodContextMode(args.method_context_mode)
    reasoning_contract_mode = ReasoningContractMode(args.reasoning_contract_mode)
    evaluation_app_config = build_agent_eval_app_config(
        get_app_config(),
        subagent_mode=args.subagent_mode,
        max_subagent_steps=args.max_subagent_steps,
        max_subagent_tokens=args.max_subagent_tokens,
    )
    subagent_runtime_limits: dict[str, int] = {}
    if subagent_enabled:
        subagent_runtime_limits = {
            "max_concurrent_subagents": (_INCUBATION_TEAM_MAX_CONCURRENT if args.subagent_mode in _TEAM_SUBAGENT_MODES else 1),
            "max_total_subagents": evaluation_app_config.subagents.max_total_per_run,
        }
    client = build_agent_eval_client(
        method_context_mode=method_context_mode,
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
        method_context_mode=method_context_mode,
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
            reasoning_contract_mode=reasoning_contract_mode,
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
        task_mode=task_mode,
        method_context_mode=method_context_mode,
        reasoning_contract_mode=reasoning_contract_mode,
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
                prompt = build_agent_eval_prompt(
                    trial,
                    task_mode=task_mode,
                    subagent_mode=args.subagent_mode,
                    reasoning_contract_mode=reasoning_contract_mode,
                )
                thread_id = build_trial_thread_id(
                    run_id=run_id,
                    case_id=trial.case.case_id,
                )
                collector = AgentEventCollector()
                task_statuses: dict[str, str] = {}
                started_at = datetime.now(UTC)
                terminal_error_code: str | None = None
                try:
                    for event in client.stream(
                        prompt,
                        thread_id=thread_id,
                        user_id=actor_id,
                        recursion_limit=args.max_agent_steps,
                        **subagent_runtime_limits,
                    ):
                        _capture_terminal_task_status(task_statuses, event)
                        collector.consume(event)
                except Exception as error:
                    terminal_error_code = _error_code(error)
                observation = collector.finish()
                if terminal_error_code is None and args.subagent_mode in _TEAM_SUBAGENT_MODES:
                    terminal_error_code = _incubation_team_protocol_error(
                        observation.events,
                        task_statuses=task_statuses,
                        project_id=trial.project_id,
                        expected_names=_team_specialist_names(args.subagent_mode),
                    )
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
