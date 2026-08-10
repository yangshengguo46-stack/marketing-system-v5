"""Comparable context assembly for the five incubation architecture candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from mcn_incubation.agent_contract import INCUBATION_AGENT_CONTRACT
from mcn_incubation.domain import (
    CaseEpisode,
    IncubationBrief,
    MethodCard,
    ProjectTruth,
)
from mcn_incubation.memory import CaseMemory, CaseQuery
from mcn_incubation.methods import MethodLibrary

LEAD_AGENT_CONSTITUTION = f"""You are the single lead MCN incubation agent for people, brands,
products, and organizations.

{INCUBATION_AGENT_CONTRACT}"""

V4_NEGATIVE_CONTROL = """按九个固定阶段依次工作：证据收集、人物模型、商业模型、对标研究、
定位候选、启动包、试验运行、商业信号、放大。首阶段不可跳过；每次只允许前进一步；
必须补齐人口字段、三个对标角色、二至三个定位候选、至少三个试验、三个名称、两个简介和三个置顶内容。"""


class ArchitectureVariant(StrEnum):
    V4_FIXED_WORKFLOW = "v4_fixed_workflow"
    LONG_PROMPT_FULL_HANDBOOK = "long_prompt_full_handbook"
    THIN_PROMPT_ON_DEMAND_METHODS = "thin_prompt_on_demand_methods"
    THIN_PROMPT_METHODS_TRUTH = "thin_prompt_methods_truth"
    THIN_PROMPT_METHODS_TRUTH_CASES = "thin_prompt_methods_truth_cases"


@dataclass(frozen=True, slots=True)
class ContextRequest:
    prompt: str
    brief: IncubationBrief
    truths: tuple[ProjectTruth, ...] = field(default_factory=tuple)
    method_query: str = ""
    case_query: CaseQuery | None = None


@dataclass(frozen=True, slots=True)
class ContextBundle:
    variant: ArchitectureVariant
    constitution: str
    method_cards: tuple[MethodCard, ...]
    truths: tuple[ProjectTruth, ...]
    cases: tuple[CaseEpisode, ...]
    fixed_workflow: str | None
    rendered_context: str
    estimated_chars: int
    context_budget_chars: int
    omitted_sections: tuple[str, ...]


def _render_brief(brief: IncubationBrief) -> str:
    return (
        "项目简报："
        f"主体类型={brief.subject_kind.value if brief.subject_kind else '未知'}；"
        f"主体={brief.subject_summary or '未知'}；"
        f"资产={list(brief.available_assets)}；能力={list(brief.capabilities)}；"
        f"产品={list(brief.offers)}；限制={list(brief.constraints)}；"
        f"目标={list(brief.goals)}；缺失={list(brief.missing_fields)}"
    )


def _render_method(card: MethodCard) -> str:
    return f"方法[{card.capability}] {card.title}：视角={list(card.lens)}；证据={list(card.evidence_needs)}；反例={list(card.counterexamples)}"


def _render_truth(truth: ProjectTruth) -> str:
    return f"事实[{truth.kind.value}/{truth.truth_id}] {truth.statement}"


def _render_case(case: CaseEpisode, *, role: str) -> str:
    return f"案例[{role}/{case.case_episode_id}/{case.status.value}] 条件={list(case.conditions)}；支持={list(case.supports_claims)}；反证={list(case.contradicts_claims)}；限制={list(case.limitations)}"


class ContextAssembler:
    """Build comparable candidate contexts under one explicit character budget."""

    def __init__(
        self,
        *,
        method_library: MethodLibrary,
        case_memory: CaseMemory,
        max_context_chars: int,
    ) -> None:
        if max_context_chars < 1_000:
            raise ValueError("max_context_chars must leave room for a useful task")
        self._methods = method_library
        self._cases = case_memory
        self._budget = max_context_chars

    def assemble(
        self,
        *,
        variant: ArchitectureVariant,
        request: ContextRequest,
    ) -> ContextBundle:
        fixed_workflow = V4_NEGATIVE_CONTROL if variant is ArchitectureVariant.V4_FIXED_WORKFLOW else None
        if variant is ArchitectureVariant.LONG_PROMPT_FULL_HANDBOOK:
            candidate_methods = self._methods.cards
        elif variant in {
            ArchitectureVariant.THIN_PROMPT_ON_DEMAND_METHODS,
            ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH,
            ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH_CASES,
        }:
            candidate_methods = self._methods.search(
                query=request.method_query or request.prompt,
                limit=3,
            )
        else:
            candidate_methods = ()

        candidate_truths = (
            request.truths
            if variant
            in {
                ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH,
                ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH_CASES,
            }
            else ()
        )
        supporting_cases: tuple[CaseEpisode, ...] = ()
        counter_cases: tuple[CaseEpisode, ...] = ()
        if variant is ArchitectureVariant.THIN_PROMPT_METHODS_TRUTH_CASES and request.case_query is not None:
            recall = self._cases.recall(request.case_query)
            supporting_cases = recall.supporting
            counter_cases = recall.counterexamples

        sections = [LEAD_AGENT_CONSTITUTION, f"用户任务：{request.prompt}", _render_brief(request.brief)]
        if fixed_workflow is not None:
            sections.append(f"失败基线流程：{fixed_workflow}")
        selected_methods: list[MethodCard] = []
        selected_truths: list[ProjectTruth] = []
        selected_cases: list[CaseEpisode] = []
        omitted: list[str] = []

        def add(label: str, text: str) -> bool:
            candidate = "\n\n".join((*sections, text))
            if len(candidate) > self._budget:
                omitted.append(label)
                return False
            sections.append(text)
            return True

        for card in candidate_methods:
            if add(f"method:{card.method_card_id}", _render_method(card)):
                selected_methods.append(card)
        for truth in candidate_truths:
            if add(f"truth:{truth.truth_id}", _render_truth(truth)):
                selected_truths.append(truth)
        for case in supporting_cases:
            if add(f"case:{case.case_episode_id}", _render_case(case, role="support")):
                selected_cases.append(case)
        for case in counter_cases:
            if add(f"case:{case.case_episode_id}", _render_case(case, role="counter")):
                selected_cases.append(case)

        rendered = "\n\n".join(sections)
        return ContextBundle(
            variant=variant,
            constitution=LEAD_AGENT_CONSTITUTION,
            method_cards=tuple(selected_methods),
            truths=tuple(selected_truths),
            cases=tuple(selected_cases),
            fixed_workflow=fixed_workflow,
            rendered_context=rendered,
            estimated_chars=len(rendered),
            context_budget_chars=self._budget,
            omitted_sections=tuple(omitted),
        )


__all__ = [
    "ArchitectureVariant",
    "ContextAssembler",
    "ContextBundle",
    "ContextRequest",
    "LEAD_AGENT_CONSTITUTION",
]
