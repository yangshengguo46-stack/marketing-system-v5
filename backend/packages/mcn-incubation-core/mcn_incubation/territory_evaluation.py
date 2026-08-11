"""Isolated contrast cases and contexts for the content-territory candidate."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

from mcn_incubation.context import LEAD_AGENT_CONSTITUTION


class TerritoryEvalVariant(StrEnum):
    BASELINE = "baseline"
    CONTENT_WORLD_OPERATORS = "content_world_operators"
    TERRITORY_METHOD = "territory_method"
    TERRITORY_METHOD_V2 = "territory_method_v2"
    TERRITORY_METHOD_V2_MECHANISMS = "territory_method_v2_mechanisms"
    TERRITORY_TWO_PASS_MECHANISMS = "territory_two_pass_mechanisms"


class ResponseMode(StrEnum):
    STRUCTURED_JSON = "structured_json"
    NATURAL_JUDGMENT = "natural_judgment"
    CONTENT_WORLD_EXPLORATION = "content_world_exploration"


@dataclass(frozen=True, slots=True)
class HumanMechanismCard:
    mechanism_id: str
    title: str
    search_terms: tuple[str, ...]
    observations: tuple[str, ...]
    limitations: tuple[str, ...]
    source_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("mechanism_id", "title"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be blank")
        for field_name in (
            "search_terms",
            "observations",
            "limitations",
            "source_refs",
        ):
            values = getattr(self, field_name)
            if not values or any(not value.strip() for value in values):
                raise ValueError(f"{field_name} must contain nonblank values")


class TerritoryMechanismLibrary:
    """Retrieve general observations without routing or selecting a strategy."""

    def __init__(self, cards: tuple[HumanMechanismCard, ...]) -> None:
        if len({card.mechanism_id for card in cards}) != len(cards):
            raise ValueError("mechanism card ids must be unique")
        self._cards = cards

    @property
    def cards(self) -> tuple[HumanMechanismCard, ...]:
        return self._cards

    def search(self, *, query: str, limit: int) -> tuple[HumanMechanismCard, ...]:
        if limit < 1:
            raise ValueError("mechanism search limit must be positive")
        normalized = query.casefold()
        ranked: list[tuple[int, str, HumanMechanismCard]] = []
        for card in self._cards:
            score = sum(term.casefold() in normalized for term in card.search_terms)
            if score:
                ranked.append((score, card.mechanism_id, card))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return tuple(item[2] for item in ranked[:limit])


def default_territory_mechanism_library() -> TerritoryMechanismLibrary:
    """Return narrow evaluation context; these cards are not production knowledge."""

    return TerritoryMechanismLibrary(
        (
            HumanMechanismCard(
                mechanism_id="gift-exchange-v1",
                title="礼物交换与社会关系",
                search_terms=("礼物", "礼品", "赠礼", "送礼", "收礼", "gift"),
                observations=(
                    "礼物交换不只是物品转移，也可能建立、维持或协商社会关系。",
                    "给予、接受、拒绝与回赠会受到情境、关系和互惠期待影响。",
                    "礼物可以参与表达身份、团结、纪念、责任或关系边界，但含义取决于具体文化与处境。",
                ),
                limitations=(
                    "这些是一般人类学观察，不能证明某一客户、受众或购买动机。",
                    "它们不能证明任何题材会获得流量、询盘或成交，也不能替代项目调查。",
                ),
                source_refs=(
                    "https://www.anthroencyclopedia.com/entry/gifts",
                    "https://openstax.org/books/introduction-anthropology/pages/7-6-exchange-value-and-consumption",
                ),
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class TerritoryContrastCase:
    case_id: str
    contrast_group: str
    surface_label: str
    review_status: str
    subject_lenses: tuple[str, ...]
    known_facts: tuple[str, ...]
    business_goal: tuple[str, ...]
    must_change: tuple[str, ...]
    mutation: str

    def __post_init__(self) -> None:
        for field_name in (
            "case_id",
            "contrast_group",
            "surface_label",
            "review_status",
            "mutation",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be blank")
        if not self.known_facts:
            raise ValueError("known_facts cannot be empty")
        if not self.business_goal:
            raise ValueError("business_goal cannot be empty")


@dataclass(frozen=True, slots=True)
class TerritoryAnchorCase:
    case_id: str
    review_status: str
    subject_kind: str
    request: str
    known_facts: tuple[str, ...]
    observable_success: tuple[str, ...]
    observable_failures: tuple[str, ...]
    mutation: str
    expert_anchor: Mapping[str, object]

    def __post_init__(self) -> None:
        for field_name in (
            "case_id",
            "review_status",
            "subject_kind",
            "request",
            "mutation",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be blank")
        if not self.known_facts:
            raise ValueError("known_facts cannot be empty")
        object.__setattr__(self, "expert_anchor", MappingProxyType(dict(self.expert_anchor)))


def _strings(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field_name} must be a nonblank string list")
    return tuple(value)


def load_territory_contrast_cases(path: Path) -> tuple[TerritoryContrastCase, ...]:
    """Load review-only cases without treating their rubric notes as model context."""

    cases: list[TerritoryContrastCase] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        raw = json.loads(raw_line)
        if not isinstance(raw, dict):
            raise ValueError(f"territory eval line {line_number} must be an object")
        cases.append(
            TerritoryContrastCase(
                case_id=str(raw["case_id"]),
                contrast_group=str(raw["contrast_group"]),
                surface_label=str(raw["surface_label"]),
                review_status=str(raw["review_status"]),
                subject_lenses=_strings(raw["subject_lenses"], field_name="subject_lenses"),
                known_facts=_strings(raw["known_facts"], field_name="known_facts"),
                business_goal=_strings(raw["business_goal"], field_name="business_goal"),
                must_change=_strings(raw["must_change"], field_name="must_change"),
                mutation=str(raw["mutation"]),
            )
        )
    if not cases:
        raise ValueError("territory contrast corpus cannot be empty")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("territory contrast case ids must be unique")
    return tuple(cases)


def load_territory_anchor_cases(path: Path) -> tuple[TerritoryAnchorCase, ...]:
    """Load adjudication data while keeping expert answers separate from prompts."""

    cases: list[TerritoryAnchorCase] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        raw = json.loads(raw_line)
        if not isinstance(raw, dict):
            raise ValueError(f"territory anchor line {line_number} must be an object")
        raw_anchor = raw.get("expert_anchor", {})
        if not isinstance(raw_anchor, dict):
            raise ValueError(f"expert_anchor on line {line_number} must be an object")
        cases.append(
            TerritoryAnchorCase(
                case_id=str(raw["case_id"]),
                review_status=str(raw["review_status"]),
                subject_kind=str(raw["subject_kind"]),
                request=str(raw["request"]),
                known_facts=_strings(raw["known_facts"], field_name="known_facts"),
                observable_success=_strings(
                    raw["observable_success"],
                    field_name="observable_success",
                ),
                observable_failures=_strings(
                    raw["observable_failures"],
                    field_name="observable_failures",
                ),
                mutation=str(raw["mutation"]),
                expert_anchor=raw_anchor,
            )
        )
    if not cases:
        raise ValueError("territory anchor corpus cannot be empty")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("territory anchor case ids must be unique")
    return tuple(cases)


COMMON_SYSTEM_CONTEXT = f"""{LEAD_AGENT_CONSTITUTION}

This is an isolated incubation judgment, not a fixed workflow. Base recommendations on the
supplied project facts, distinguish facts from hypotheses and unknowns, and keep alternatives
alive when evidence is incomplete. Do not invent research, customers, performance, prices, or
results. Do not default to talking-head delivery merely because the subject is a person. The
marketing judgment remains yours; the requested JSON shape is a record format, not a score gate."""

TERRITORY_METHOD_CARD = """<content_territory_method>
Candidate version: 1.
Find defensible content territories before choosing recurring formats or topics.
- Keep the operating subject, commercial offer, and expression carrier distinct.
- Use only the relevant person, offer, place, production-source, or organization lenses; these
  are optional views, not industry classes or mandatory steps.
- From supplied facts, derive readable bridges from event or exchange situations to the human
  task, then to a territory broad enough to produce recurring situations.
- Preserve more than one materially different candidate when plausible. For each, explain why
  this subject can credibly and sustainably own it and how audiences can attribute the value
  back to the account and business.
- Select provisionally using the business goal, available proof, production constraints, and
  monetization continuity. Keep unsupported links as unknowns and propose a small discriminating
  experiment instead of filling gaps with a generic template.
</content_territory_method>"""

TERRITORY_METHOD_SOURCE_REFS = (
    "https://www.christenseninstitute.org/theory/jobs-to-be-done/",
    "https://marketingscience.info/news-and-insights/category-entry-points-in-a-business-to-business-b2b-world",
    "https://brenocon.com/Fillmore%201982_2up.pdf",
    "https://doi.org/10.1080/00218499.1988.12467766",
)

TERRITORY_METHOD_V2_CARD = """<content_territory_method_v2>
这是发散与取舍的思考镜头，不是固定流程，也不是必须填满的表。

不要停在“介绍这个品类、分享技巧、记录日常”这一层。根据当前事实，寻找供给进入真实生活后反复发生的使用、选择、交换、关系、协作、等待、风险与结果；再判断其中哪些人类处境既有长期题材，又与经营目标相连。

只组合当前真正相关的人物、商品或服务、场所、生产源头、组织镜头。至少考虑第一反应之外是否存在一个语义更宽但仍可归因的方向：具体商品不必句句出现，观众却必须能够理解这个主体为什么有资格讲、它提供什么价值、需要时为什么会回来找它。

用三个反问淘汰空洞路线：换成任意同行是否仍完全成立；主体是否拥有持续的一手事实、判断或场景；内容积累的是泛流量，还是能回到识别、信任、询盘、购买或当前经营目标。候选之间应当是不同的战略取舍，而不是同一路线换栏目名。

信息不足时保留候选和关键未知。不要擅自补人口统计、价格、频率、流量阈值、客户结果、产品线或平台规则；呈现形式和变现只能写成与已知资源匹配的暂定方案与最小验证。
</content_territory_method_v2>"""

CONTENT_WORLD_OPERATOR_CARD = """<content_world_operators>
候选版本：conversation-v1。
这是帮助你打开内容世界的可选思考算子，不是固定流程，也不是必须逐项填写的矩阵。只组合当前真正有帮助的方向，先探索，再由你根据项目事实和经营目标取舍。

- 向上抽象：从具体对象寻找它所属的品类、反复行为、人类任务、关系或更大的生活系统。每次上移都要说明语义桥，不能用“更宏大”代替关联。
- 向下拆分：把过大的母世界拆成具有独立知识、人物、生产、使用或文化的子世界。子世界是候选节点，不是自动成为最终定位的商品目录。
- 横向展开：围绕母世界或子世界，从时间 × 空间 × 事件 × 人物 × 冲突打开可持续题材。五个维度用于发现遗漏，不要求全部出现，也不能把没有依据的故事写成事实。
- 跨维连接：在现实、历史、神话、影视、游戏和未来世界之间寻找结构相似的角色、规则、事件或象征。必须说明对象在目标世界中承担什么作用；只有同名或热点不算连接。

先保留少量语义桥真正不同的候选，避免把前一个案例的好答案机械迁移到当前主体。每个候选说明：它如何从已知事实长出来；主体能否持续接触、观察、证明或参与；受众为什么关心；内容价值如何自然回到账号与生意；最强反例、漂移风险和会改变判断的未知是什么。

可以用模型已有知识产生创意假设，但历史、作品、文化、产业和当前市场主张在核验前只能标为待研究。信息不足时先给条件化候选和一个高信息问题，不得补造客户、素材、能力、表现形式、产品、价格、频率、指标或结果。
</content_world_operators>"""

CONTENT_WORLD_EXPLORATION_CONTEXT = """<read_only_content_world_explorer>
这是一次只读的内容世界探索，供唯一 Lead 后续判断，不是面向客户的起号方案。

这一遍只回答：从已给主体或商业对象出发，有哪些语义连续的更大世界、子世界、横向切面和跨界连接值得 Lead 再考察。保留多个真正不同的分支、语义桥、反例和未知，不代替 Lead 选最终路线。

这一遍不决定账号服务谁、如何呈现、如何成交、发什么平台或先做哪个运营试验。不因为信息稀疏就用常见账号类型补齐答案。

严格区分输入事实、语义推断、模型知识产生的创意假设、需要外查的主张和未知。不得补造客户、订单、能力、资源、作品、历史事实或市场结论。
</read_only_content_world_explorer>"""

CONTENT_WORLD_EXPLORATION_OPERATOR_CARD = """<content_world_exploration_operators>
候选版本：conversation-v2。这些是打开语义搜索空间的可选算子，不是固定步骤，也不要为了填满而全部使用。

- 向上抽象：从具体对象寻找它所属的品类、反复行为、人类任务、关系或更大生活系统。每次上移都要写出中间的语义桥。
- 向下拆分：把过大的母世界拆成具有独立知识、人物、生产、使用或文化的子世界。子世界只是地图节点，不是自动答案。
- 横向展开：围绕母世界或子世界，用时间 × 空间 × 事件 × 人物 × 冲突发现未被看见的切面，不要把假设写成真实故事。
- 跨维连接：在现实、历史、神话、影视、游戏和未来世界之间寻找结构相似的角色、规则、事件或象征，并说明结构对应；只有同名或热点不算连接。

不把前一个案例的优秀路径机械迁移给当前对象。输出简洁的地图笔记：起点词义、可选节点、节点间的语义桥、可反复发生的张力、最强反例与待外查主张；不作最终取舍。
</content_world_exploration_operators>"""

OUTPUT_CONTRACT = """只输出一个有效 JSON 对象，不要 Markdown 代码围栏。结构如下；允许信息不全，禁止为了补字段而编造：
{
  "known_facts_used": ["F1"],
  "territory_candidates": [
    {
      "territory_id": "candidate-1",
      "statement": "内容领地的一句话定义",
      "lens_refs": ["实际使用的观察镜头"],
      "semantic_bridge": ["事实或供给", "反复事件或人的任务", "内容领地"],
      "recurring_situations": ["可持续发生的真实题材情境"],
      "ownership_basis": ["该主体凭什么能持续且可信地讲"],
      "attribution_path": "观众如何把内容价值归因回账号和生意",
      "fact_refs": ["F1"],
      "unknowns": ["仍需验证的连接"]
    }
  ],
  "selected_territory_id": "candidate-1 或 null",
  "incubation_route": {
    "subject": "真正运营和被记住的主体",
    "expression_carrier": "与资源和表现能力匹配的呈现方式",
    "intended_public": "当前暂定受众及其处境",
    "content_engine": "如何持续产生内容而非几个选题",
    "monetization_path": "从第一版开始存在的变现假设",
    "conversion_path": "内容如何积累信任并承接行动"
  },
  "alternatives": ["未选路线及未选原因"],
  "key_unknowns": ["关键未知"],
  "first_experiment": {
    "hypothesis": "最值得先验证的判断",
    "content_variants": ["低成本且能区分候选的内容变量"],
    "business_signals": ["除播放量之外的观察信号"]
  }
}"""

NATURAL_RESPONSE_CONTRACT = """请像一位负责结果的 MCN 孵化负责人，直接向客户讲清当前判断，不要解释内部方法，也不要输出 JSON 或照着固定表格填空。

先指出决定方向的项目事实，再给出当前真正有意义的内容领地候选和取舍。候选只有一个也可以，有多个时必须是不同战略，而不是换栏目名。说明内容为什么能长期生长、主体凭什么拥有、观众如何把价值归因回账号与生意，并给出与现有资源匹配的表现形式和从第一版开始存在的变现假设。

把用户事实、你的推断、关键未知分清。没有依据的年龄、价格、频率、转化数字、客户结果、产品或平台结论一律不补；不要为了完整而补齐。最后只提出能区分候选或验证商业连接的最小实验。"""


def render_mechanism_context(cards: tuple[HumanMechanismCard, ...]) -> str:
    sections = [
        "<human_mechanism_context>",
        "这些观察不是当前客户事实，也不是营销答案；只能作为发散材料，并受各自限制约束。",
    ]
    for card in cards:
        sections.extend(
            (
                f"机制[{card.mechanism_id}] {card.title}",
                f"观察：{'；'.join(card.observations)}",
                f"限制：{'；'.join(card.limitations)}",
                f"来源：{'；'.join(card.source_refs)}",
            )
        )
    sections.append("</human_mechanism_context>")
    return "\n".join(sections)


def render_territory_explorer_context(mechanism_query: str) -> str:
    cards = default_territory_mechanism_library().search(
        query=mechanism_query,
        limit=2,
    )
    mechanism_context = render_mechanism_context(cards) if cards else ""
    sections = [
        """<read_only_territory_explorer>
这是一个只读内容领地探索任务。你只能给唯一 Lead 提供候选与反证，不得修改项目事实，不要替 Lead 做最终选择，也不得直接向用户交付孵化方案。

从已给事实出发，把商业供给放回使用、选择、交换、关系、协作、等待、风险和结果等事件中。寻找第一反应之外、语义更宽但仍能回到主体能力与商业归因的候选。候选应解释品类行为或人的反复处境、长期题材来源、主体拥有权、归因路径、事实依据、关键未知和最强反例。

不要设计表现形式、发布频率、价格、产品线、平台动作、指标阈值或最终变现方案。不要虚构客户、订单、案例、资质、场地、素材和结果。输出供 Lead 思考的简洁候选笔记，不要写成面向客户的成品答案。
</read_only_territory_explorer>""",
        TERRITORY_METHOD_V2_CARD,
        mechanism_context,
    ]
    return "\n\n".join(section for section in sections if section)


def render_system_context(
    variant: TerritoryEvalVariant,
    *,
    mechanism_query: str = "",
    response_mode: ResponseMode = ResponseMode.STRUCTURED_JSON,
) -> str:
    if response_mode is ResponseMode.CONTENT_WORLD_EXPLORATION:
        if variant is TerritoryEvalVariant.BASELINE:
            return CONTENT_WORLD_EXPLORATION_CONTEXT
        if variant is TerritoryEvalVariant.CONTENT_WORLD_OPERATORS:
            return f"{CONTENT_WORLD_EXPLORATION_CONTEXT}\n\n{CONTENT_WORLD_EXPLORATION_OPERATOR_CARD}"
        raise ValueError("content-world exploration supports only baseline and content_world_operators variants")
    if variant is TerritoryEvalVariant.BASELINE:
        return COMMON_SYSTEM_CONTEXT
    if variant is TerritoryEvalVariant.CONTENT_WORLD_OPERATORS:
        return f"{COMMON_SYSTEM_CONTEXT}\n\n{CONTENT_WORLD_OPERATOR_CARD}"
    if variant is TerritoryEvalVariant.TERRITORY_METHOD:
        return f"{COMMON_SYSTEM_CONTEXT}\n\n{TERRITORY_METHOD_CARD}"
    if variant is TerritoryEvalVariant.TERRITORY_METHOD_V2:
        return f"{COMMON_SYSTEM_CONTEXT}\n\n{TERRITORY_METHOD_V2_CARD}"
    if variant in {
        TerritoryEvalVariant.TERRITORY_METHOD_V2_MECHANISMS,
        TerritoryEvalVariant.TERRITORY_TWO_PASS_MECHANISMS,
    }:
        cards = default_territory_mechanism_library().search(
            query=mechanism_query,
            limit=2,
        )
        mechanism_context = render_mechanism_context(cards) if cards else ""
        return "\n\n".join(
            section
            for section in (
                COMMON_SYSTEM_CONTEXT,
                TERRITORY_METHOD_V2_CARD,
                mechanism_context,
            )
            if section
        )
    raise ValueError(f"unsupported territory eval variant: {variant}")


def render_case_message(
    case: TerritoryContrastCase,
    *,
    include_mutation: bool,
    response_mode: ResponseMode = ResponseMode.STRUCTURED_JSON,
) -> str:
    sections = [render_case_evidence_message(case, include_mutation=include_mutation)]
    if response_mode is ResponseMode.CONTENT_WORLD_EXPLORATION:
        pass
    elif response_mode is ResponseMode.STRUCTURED_JSON:
        sections.append(OUTPUT_CONTRACT)
    elif response_mode is ResponseMode.NATURAL_JUDGMENT:
        sections.append(NATURAL_RESPONSE_CONTRACT)
    else:
        raise ValueError(f"unsupported response mode: {response_mode}")
    return "\n\n".join(sections)


def render_case_evidence_message(
    case: TerritoryContrastCase,
    *,
    include_mutation: bool,
) -> str:
    facts = "\n".join(f"- F{index}: {fact}" for index, fact in enumerate(case.known_facts, start=1))
    goals = "\n".join(f"- {goal}" for goal in case.business_goal)
    sections = [
        "请为这个主体给出起号、持续内容与变现相连的孵化判断。",
        f"用户当前使用的表面称呼：{case.surface_label}",
        f"已知项目事实：\n{facts}",
        f"经营目标：\n{goals}",
    ]
    if include_mutation:
        sections.append(f"刚出现的新事实或结果：{case.mutation}")
    return "\n\n".join(sections)


def render_anchor_message(
    case: TerritoryAnchorCase,
    *,
    include_mutation: bool,
    response_mode: ResponseMode = ResponseMode.NATURAL_JUDGMENT,
) -> str:
    sections = [render_anchor_evidence_message(case, include_mutation=include_mutation)]
    if response_mode is ResponseMode.CONTENT_WORLD_EXPLORATION:
        pass
    elif response_mode is ResponseMode.STRUCTURED_JSON:
        sections.append(OUTPUT_CONTRACT)
    elif response_mode is ResponseMode.NATURAL_JUDGMENT:
        sections.append(NATURAL_RESPONSE_CONTRACT)
    else:
        raise ValueError(f"unsupported response mode: {response_mode}")
    return "\n\n".join(sections)


def render_anchor_evidence_message(
    case: TerritoryAnchorCase,
    *,
    include_mutation: bool,
) -> str:
    facts = "\n".join(f"- F{index}: {fact}" for index, fact in enumerate(case.known_facts, start=1))
    sections = [
        f"用户原始请求：{case.request}",
        f"当前明确知道的项目事实：\n{facts}",
    ]
    if include_mutation:
        sections.append(f"刚出现的新事实或结果：{case.mutation}")
    return "\n\n".join(sections)


__all__ = [
    "COMMON_SYSTEM_CONTEXT",
    "CONTENT_WORLD_EXPLORATION_CONTEXT",
    "CONTENT_WORLD_EXPLORATION_OPERATOR_CARD",
    "CONTENT_WORLD_OPERATOR_CARD",
    "HumanMechanismCard",
    "NATURAL_RESPONSE_CONTRACT",
    "OUTPUT_CONTRACT",
    "ResponseMode",
    "TERRITORY_METHOD_CARD",
    "TERRITORY_METHOD_SOURCE_REFS",
    "TERRITORY_METHOD_V2_CARD",
    "TerritoryAnchorCase",
    "TerritoryContrastCase",
    "TerritoryEvalVariant",
    "TerritoryMechanismLibrary",
    "default_territory_mechanism_library",
    "load_territory_anchor_cases",
    "load_territory_contrast_cases",
    "render_anchor_message",
    "render_anchor_evidence_message",
    "render_case_message",
    "render_case_evidence_message",
    "render_mechanism_context",
    "render_territory_explorer_context",
    "render_system_context",
]
