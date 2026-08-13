from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.constants import TAG_NOSTREAM

from deerflow.tools.builtins.content_world_explorer_tool import (
    CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT,
    build_content_world_explorer_tool,
    build_content_world_messages,
    parse_content_world_exploration,
    project_content_world_map,
    validate_content_world_root_against_semantics,
)
from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[tuple[list[object], dict | None]] = []

    async def ainvoke(self, messages, config=None):
        self.calls.append((list(messages), config))
        return self.replies.pop(0)


class SecondCallFailureModel(FakeModel):
    async def ainvoke(self, messages, config=None):
        self.calls.append((list(messages), config))
        if len(self.calls) == 2:
            raise RuntimeError("provider rejected PRIVATE_CREDENTIAL_MARKER")
        return self.replies.pop(0)


def _valid_semantics() -> dict[str, object]:
    return {
        "known_facts": ["主体从事一种组合品类的生产"],
        "commercial_expression": "属性品类生产",
        "plain_paraphrases": ["主体生产一种带有属性的品类"],
        "offer_object": {
            "term": "属性品类",
            "semantic_head": "品类",
            "support": "lexical_semantics",
            "basis": "品类决定组合表达所属类别",
        },
        "operating_containers": [],
        "qualifiers": [
            {
                "term": "属性",
                "relation": "material_or_attribute",
                "target": "品类",
                "support": "lexical_semantics",
                "basis": "属性修饰品类",
            }
        ],
        "seller_activities": [
            {
                "activity": "生产",
                "target": "属性品类",
                "support": "explicit",
                "basis": "来自用户原话",
            }
        ],
        "constitutive_functions": [
            {
                "function": "完成该品类通常承担的功能",
                "support": "lexical_semantics",
                "basis": "品类词义支持",
            }
        ],
        "buyer_progresses": [
            {
                "progress": "借助该品类完成对应任务",
                "support": "lexical_semantics",
                "basis": "通用品类语义，不是实际客户事实",
            }
        ],
        "ambiguities": ["实际交易的是成品还是生产服务未知"],
        "insufficiency": None,
    }


def _valid_exploration() -> dict[str, object]:
    return {
        "content_world_root": {
            "term": "品类",
            "relation_to_commercial_object": "属性品类本身就是一个可持续展开的完整对象世界",
            "selection_basis": "保留已有容量的具体品类，不用泛化概念替换",
            "purpose_world_checks": [],
            "modifier_handling": [
                {
                    "term": "属性",
                    "without_modifier_root": "品类",
                    "complete_without_modifier": True,
                    "constitutive_function_preserved": True,
                    "return_path": "品类世界可通过属性分支自然回到属性品类",
                    "basis": "去掉属性后品类仍是完整且可归因的具体世界",
                }
            ],
        },
        "downward_expansion": [
            {
                "branch": "品类内部的不同子类",
                "support": "lexical_semantics",
                "basis": "从语义主词的下位概念展开",
            }
        ],
        "upward_expansion": [
            {
                "source": "品类",
                "target": "该品类服务的长期任务",
                "relation": "从对象追问其被使用来完成什么",
                "business_specificity": "retained",
            }
        ],
        "horizontal_expansion": {
            "time_and_history": ["形成、历史变化与未来走向"],
            "geography_and_environment": ["不同地域和环境中的差异"],
            "culture_and_habits": ["不同地方如何理解、使用并形成生活习惯"],
            "people": ["生产者、使用者与受影响者"],
            "events": ["该品类进入真实生活的节点"],
            "conflicts": ["效率、质量与代价之间的矛盾"],
        },
        "comparative_scope_checks": [
            {
                "scope": "countries",
                "status": "connected",
                "direction": "不同国家如何理解和使用该品类",
                "basis": "该品类存在跨国使用和文化差异",
            },
            {
                "scope": "regions",
                "status": "connected",
                "direction": "不同地区的环境和习惯如何改变该品类",
                "basis": "地理和环境与品类使用有结构关系",
            },
            {
                "scope": "ethnic_and_cultural_groups",
                "status": "connected",
                "direction": "不同民族与文化群体围绕该品类形成什么习惯",
                "basis": "群体文化实践与品类有可研究连接，不归因于生物属性",
            },
        ],
        "cross_domain_connections": [
            {
                "domain": "历史与文化",
                "connection": "研究该品类如何进入不同时代的生活",
                "research_needed": True,
            }
        ],
        "insufficiency": None,
    }


def _parsed_exploration() -> dict[str, object]:
    return parse_content_world_exploration(json.dumps(_valid_exploration(), ensure_ascii=False))


def _runtime(*, journal=None, messages=None) -> ToolRuntime:
    context = {}
    if journal is not None:
        context["__run_journal"] = journal
    return ToolRuntime(
        state={"messages": list(messages or [])},
        context=context,
        config={"tags": ["root-run"]},
        stream_writer=lambda _: None,
        tool_call_id="world-call",
        store=None,
        tools=[],
    )


def test_explorer_prompt_expands_a_content_world_without_selecting_the_account_route():
    prompt = CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT

    for required in (
        "向下拆分",
        "向上抽象",
        "时间与历史、地理与环境、文化与生活习惯、人物、事件与冲突",
        "跨领域连接",
        "内容世界",
        "能力证明",
    ):
        assert required in prompt
    assert "不是最终答题 Agent" in prompt
    assert "不得选择最终定位" in prompt
    assert "不得把生产过程" in prompt
    assert "待研究方向" in prompt
    assert "research_needed` 必须为 `true`" in prompt
    assert "只输出内容根与展开地图" in prompt
    for leaked_case in ("黄金", "礼品", "水果", "海鲜", "宝妈", "榴莲"):
        assert leaked_case not in prompt


def test_explorer_prompt_does_not_shift_attention_to_selling_or_monetization():
    prompt = CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT

    for out_of_scope_term in (
        "卖货",
        "售卖",
        "销售",
        "广告",
        "变现",
        "成交",
        "转化",
        "客单",
        "复购",
        "带货",
    ):
        assert out_of_scope_term not in prompt
    assert "B/C" not in prompt
    assert '"seller_evidence"' not in prompt
    assert '"downstream_unknowns"' not in prompt


def test_explorer_prompt_preserves_a_broad_object_world_instead_of_only_near_sale_topics():
    prompt = CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT

    assert "完整对象世界" in prompt
    assert "向下、横向和跨领域" in prompt
    assert "离原始对象最近" in prompt
    assert "选购技巧" in prompt
    assert "不要求主体独占" in prompt
    assert "卖方动作" in prompt
    assert "文化与生活习惯" in prompt
    assert "只有这些机制都不会改变根世界时" in prompt
    assert "`served_object` 与 `purpose`" in prompt
    assert "被服务对象 + 专业目的/结果" in prompt
    assert "候选路线" not in prompt
    assert '"candidate_worlds"' not in prompt


def test_parser_does_not_use_a_keyword_gate_for_a_legitimate_content_subject():
    payload = _valid_exploration()
    payload["content_world_root"]["selection_basis"] = "这个业务本身研究广告内容，因此该词是内容对象而不是下游方案"

    parsed = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))

    assert "广告内容" in parsed["content_world_root"]["selection_basis"]


def test_parser_reports_missing_and_extra_fields_for_bounded_repair():
    payload = _valid_exploration()
    payload.pop("insufficiency")
    payload["unexpected_field"] = []

    with pytest.raises(ValueError) as exc_info:
        parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))

    message = str(exc_info.value)
    assert "missing: insufficiency" in message
    assert "extra: unexpected_field" in message


def test_parser_discards_only_the_two_retired_out_of_scope_fields():
    payload = _valid_exploration()
    payload["seller_evidence"] = [{"item": "旧字段内容"}]
    payload["downstream_unknowns"] = ["旧字段内容"]

    parsed = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))

    assert "seller_evidence" not in parsed
    assert "downstream_unknowns" not in parsed


def test_explorer_prompt_does_not_treat_the_lexical_head_as_the_automatic_world_root():
    prompt = CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT

    assert "语义主词不自动等于内容世界根" in prompt
    assert "配方、原料、部件、工具或中间载体" in prompt
    assert "已在商业表达中出现的具体对象或活动世界" in prompt
    assert "必须比较" in prompt
    assert "不得无条件向上替换" in prompt
    assert "泛化的体验、生活方式或情绪价值" in prompt
    assert "最小完整根" in prompt
    assert "每个修饰词" in prompt
    assert "买方为什么需要" in prompt
    assert "卖方如何制作" in prompt
    assert "修饰词专属的材料、工艺、参数" in prompt
    assert "不得与完整商品表达比较" in prompt
    assert "branch_lens" in prompt
    assert "root_essential" in prompt
    assert "国家、地区、民族与文化群体" in prompt
    assert "不得形成刻板推断" in prompt
    assert "资源与环境" in prompt
    assert "规则与禁忌" in prompt
    assert "仪式与社交组织" in prompt
    assert "工具、技法、历史传播" in prompt
    assert "任一机制会改变根世界" in prompt
    assert "缺少现成事例、资料或主体经验" in prompt


def test_explorer_messages_keep_user_input_untrusted_and_semantics_separate():
    business_context = "我经营一种产品，想做账号"
    semantics = _valid_semantics()

    messages = build_content_world_messages(
        business_context=business_context,
        business_semantics=semantics,
    )

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert "--- BEGIN USER INPUT ---" in messages[1].content
    assert business_context in messages[1].content
    assert "--- BEGIN VALIDATED SEMANTIC MATERIAL ---" in messages[1].content
    assert json.dumps(semantics, ensure_ascii=False, separators=(",", ":")) in messages[1].content
    assert messages[1].additional_kwargs["original_user_content"] == business_context


def test_exploration_parser_accepts_variable_world_count_and_rejects_schema_drift():
    payload = _valid_exploration()
    parsed = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    assert parsed["content_world_root"]["modifier_handling"][0]["decision"] == "branch_lens"
    assert {key: value for key, value in parsed.items() if key != "content_world_root"} == {key: value for key, value in payload.items() if key != "content_world_root"}

    payload["insufficiency"] = "没有可解释的商业对象"
    assert parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))["insufficiency"] == "没有可解释的商业对象"

    payload["unexpected"] = "drift"
    try:
        parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    except ValueError as exc:
        assert "exactly" in str(exc)
    else:
        raise AssertionError("schema drift was accepted")


def test_exploration_parser_derives_purpose_world_promotion_from_evidence():
    payload = _valid_exploration()
    payload["content_world_root"]["purpose_world_checks"] = [
        {
            "term": "活动",
            "product_role": "intermediate_enabler",
            "world_complete": True,
            "capacity_relation": "broader",
            "return_path": "活动的关键实现环节会自然回到该商品",
            "basis": "商品形态的材料、工艺与用法均被活动世界包含，活动还多出时空、文化与人物关系",
        }
    ]

    parsed = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))

    assert parsed["content_world_root"]["purpose_world_checks"][0]["decision"] == "promote_to_root"


def test_root_validator_rejects_an_enabling_product_when_its_purpose_world_wins():
    payload = _valid_exploration()
    payload["content_world_root"] = {
        "term": "活动配方",
        "relation_to_commercial_object": "它是用于完成活动的商品配方",
        "selection_basis": "配方距离商品更近",
        "purpose_world_checks": [
            {
                "term": "活动",
                "product_role": "intermediate_enabler",
                "world_complete": True,
                "capacity_relation": "broader",
                "return_path": "活动通过地域风格与配方分支回到商品",
                "basis": "活动包含配方的原料、制作和使用，还有独立的时空、文化和关系容量",
            }
        ],
        "modifier_handling": [
            {
                "term": "地域",
                "without_modifier_root": "活动配方",
                "complete_without_modifier": True,
                "constitutive_function_preserved": True,
                "return_path": "配方可回到地域活动配方",
                "basis": "地域是分支",
            },
        ],
    }
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    semantics = _valid_semantics()
    semantics["offer_object"] = {
        "term": "地域活动配方",
        "semantic_head": "配方",
        "support": "lexical_semantics",
        "basis": "配方是词法主词",
    }
    semantics["qualifiers"] = [
        {
            "term": "地域",
            "relation": "location_or_channel",
            "target": "活动配方",
            "support": "lexical_semantics",
            "basis": "地域修饰商品",
        },
        {
            "term": "活动",
            "relation": "purpose",
            "target": "配方",
            "support": "lexical_semantics",
            "basis": "配方直接用于该活动",
        },
    ]

    try:
        validate_content_world_root_against_semantics(exploration, semantics)
    except ValueError as exc:
        assert "purpose world" in str(exc)
        assert "rebuild every expansion axis" in str(exc)
    else:
        raise AssertionError("a winning purpose world was left under the enabling product")


def test_root_validator_keeps_a_complete_gift_object_below_its_gifting_action():
    payload = _valid_exploration()
    payload["content_world_root"] = {
        "term": "礼品",
        "relation_to_commercial_object": "礼品本身是被选择和赠予的完整对象",
        "selection_basis": "被用于馈赠不会把完整的礼品对象降成中间载体",
        "purpose_world_checks": [
            {
                "term": "馈赠",
                "product_role": "complete_object_or_related",
                "world_complete": True,
                "capacity_relation": "broader",
                "return_path": "馈赠选择可回到具体商品",
                "basis": "馈赠是礼品的上游行为，但礼品不是配方、原料、部件或工具",
            }
        ],
        "modifier_handling": [
            {
                "term": "属性",
                "without_modifier_root": "礼品",
                "complete_without_modifier": True,
                "constitutive_function_preserved": True,
                "return_path": "礼品可通过属性分支回到商品",
                "basis": "去掉属性后馈赠功能仍完整",
            }
        ],
    }
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    semantics = _valid_semantics()
    semantics["constitutive_functions"] = [
        {
            "function": "作为馈赠品用于人际往来",
            "support": "lexical_semantics",
            "basis": "品类词义支持",
        }
    ]
    semantics["buyer_progresses"] = [
        {
            "progress": "完成馈赠并表达心意",
            "support": "lexical_semantics",
            "basis": "通用品类语义",
        }
    ]

    validated = validate_content_world_root_against_semantics(exploration, semantics)

    assert validated["content_world_root"]["term"] == "礼品"
    assert validated["content_world_root"]["purpose_world_checks"][0]["decision"] == "keep_product_root"


def test_exploration_parser_rejects_cross_domain_claims_marked_as_already_verified():
    payload = _valid_exploration()
    payload["cross_domain_connections"][0]["research_needed"] = False

    try:
        parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    except ValueError as exc:
        assert "research_needed" in str(exc)
    else:
        raise AssertionError("an unverified cross-domain claim was accepted as verified")


def test_exploration_parser_rejects_a_branch_modifier_left_inside_the_root_term():
    payload = _valid_exploration()
    payload["content_world_root"]["term"] = "属性品类"

    try:
        parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    except ValueError as exc:
        assert "branch_lens" in str(exc)
    else:
        raise AssertionError("a branch modifier was retained inside the root term")


def test_modifier_decision_must_follow_the_complete_world_counterfactual():
    payload = _valid_exploration()
    modifier = payload["content_world_root"]["modifier_handling"][0]
    parsed = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    assert parsed["content_world_root"]["modifier_handling"][0]["decision"] == "branch_lens"

    modifier["complete_without_modifier"] = False
    modifier["constitutive_function_preserved"] = False
    modifier["return_path"] = None
    parsed = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    assert parsed["content_world_root"]["modifier_handling"][0]["decision"] == "root_essential"


def test_attribute_modifier_cannot_negate_the_base_buyer_function_with_its_own_added_value():
    payload = _valid_exploration()
    modifier = payload["content_world_root"]["modifier_handling"][0]
    modifier["constitutive_function_preserved"] = False
    payload["content_world_root"]["term"] = "属性品类"
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))

    try:
        validate_content_world_root_against_semantics(exploration, _valid_semantics())
    except ValueError as exc:
        assert "attribute-like qualifier" in str(exc)
        assert "rebuild every expansion axis" in str(exc)
    else:
        raise AssertionError("modifier-added value incorrectly negated the base buyer function")


def test_attribute_modifier_cannot_call_the_validated_semantic_head_incomplete():
    payload = _valid_exploration()
    modifier = payload["content_world_root"]["modifier_handling"][0]
    modifier["complete_without_modifier"] = False
    modifier["constitutive_function_preserved"] = False
    modifier["return_path"] = None
    payload["content_world_root"]["term"] = "属性品类"
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))

    try:
        validate_content_world_root_against_semantics(exploration, _valid_semantics())
    except ValueError as exc:
        assert "validated semantic head" in str(exc)
        assert "rebuild every expansion axis" in str(exc)
    else:
        raise AssertionError("the validated semantic head was incorrectly called an incomplete world")


def test_root_validator_discards_an_ungrounded_modifier_when_it_did_not_pollute_the_root():
    payload = _valid_exploration()
    payload["content_world_root"]["modifier_handling"].append(
        {
            "term": "下游客群简称",
            "without_modifier_root": "品类",
            "complete_without_modifier": True,
            "constitutive_function_preserved": True,
            "return_path": "品类世界自然回到商业对象",
            "basis": "模型自行把下游简称当成商品修饰",
        }
    )
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))

    validated = validate_content_world_root_against_semantics(exploration, _valid_semantics())

    assert validated["content_world_root"]["term"] == "品类"
    assert validated["content_world_root"]["modifier_handling"] == [exploration["content_world_root"]["modifier_handling"][0]]


def test_root_validator_discards_a_semantic_other_outside_the_offer_object():
    payload = _valid_exploration()
    payload["content_world_root"]["modifier_handling"][0]["term"] = "客群简称"
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    semantics = _valid_semantics()
    semantics["qualifiers"] = [
        {
            "term": "客群简称",
            "relation": "other",
            "target": "经营模式",
            "support": "lexical_semantics",
            "basis": "下游信息，不是商业对象的组成修饰",
        }
    ]

    validated = validate_content_world_root_against_semantics(exploration, semantics)

    assert validated["content_world_root"]["term"] == "品类"
    assert validated["content_world_root"]["modifier_handling"] == []


def test_root_validator_collapses_duplicate_commercial_object_qualifiers():
    payload = _valid_exploration()
    payload["content_world_root"]["modifier_handling"].append(dict(payload["content_world_root"]["modifier_handling"][0]))
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    validated = validate_content_world_root_against_semantics(exploration, _valid_semantics())

    assert len(validated["content_world_root"]["modifier_handling"]) == 1


def test_root_validator_still_rejects_an_ineligible_modifier_that_pollutes_the_root():
    payload = _valid_exploration()
    payload["content_world_root"]["term"] = "源头品类"
    payload["content_world_root"]["modifier_handling"] = [
        {
            "term": "源头",
            "without_modifier_root": "品类",
            "complete_without_modifier": False,
            "constitutive_function_preserved": True,
            "return_path": "品类仍可回到经营对象",
            "basis": "模型错误地把经营位置保留在内容根",
        }
    ]
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    semantics = _valid_semantics()
    semantics["qualifiers"] = [
        {
            "term": "源头",
            "relation": "other",
            "target": "品类",
            "support": "explicit",
            "basis": "源头是经营位置，不是商品根修饰",
        }
    ]

    try:
        validate_content_world_root_against_semantics(exploration, semantics)
    except ValueError as exc:
        assert "pollutes the root" in str(exc)
    else:
        raise AssertionError("an operating-position modifier remained inside the root")


def test_served_object_that_becomes_the_exact_root_is_not_treated_as_a_modifier():
    payload = _valid_exploration()
    payload["content_world_root"] = {
        "term": "活动",
        "relation_to_commercial_object": "商品是用于该活动的中间载体",
        "selection_basis": "活动本身是比载体更完整的内容世界",
        "purpose_world_checks": [
            {
                "term": "活动",
                "product_role": "intermediate_enabler",
                "world_complete": True,
                "capacity_relation": "broader",
                "return_path": "活动通过商品载体的实现环节回到生意",
                "basis": "活动世界包含载体的使用且有更多独立展开轴",
            }
        ],
        "modifier_handling": [
            {
                "term": "地域",
                "without_modifier_root": "活动",
                "complete_without_modifier": True,
                "constitutive_function_preserved": True,
                "return_path": "活动可通过地域分支回到地域活动载体",
                "basis": "去掉地域后活动仍是完整世界",
            }
        ],
    }
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    semantics = _valid_semantics()
    semantics["offer_object"] = {
        "term": "地域活动载体",
        "semantic_head": "载体",
        "support": "lexical_semantics",
        "basis": "载体决定商品表达的词法类别",
    }
    semantics["qualifiers"] = [
        {
            "term": "地域",
            "relation": "location_or_channel",
            "target": "活动",
            "support": "lexical_semantics",
            "basis": "地域修饰活动",
        },
        {
            "term": "活动",
            "relation": "served_object",
            "target": "载体",
            "support": "lexical_semantics",
            "basis": "载体服务于该活动",
        },
    ]

    validated = validate_content_world_root_against_semantics(exploration, semantics)

    assert validated["content_world_root"]["term"] == "活动"
    assert validated["content_world_root"]["modifier_handling"][0]["term"] == "地域"


def test_nonpromoted_served_object_is_still_classified_as_a_product_branch():
    payload = _valid_exploration()
    payload["content_world_root"] = {
        "term": "防护包装",
        "relation_to_commercial_object": "商品为外部设备提供防护，但不构成设备本身",
        "selection_basis": "保留专业任务世界，将被服务对象作为应用分支",
        "purpose_world_checks": [
            {
                "term": "设备",
                "product_role": "complete_object_or_related",
                "world_complete": True,
                "capacity_relation": "broader",
                "return_path": "设备的储运防护需求可回到防护包装",
                "basis": "防护包装保护设备，不是创造或完成设备的构成手段",
            }
        ],
        "modifier_handling": [],
    }
    exploration = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    semantics = _valid_semantics()
    semantics["offer_object"] = {
        "term": "设备防护包装",
        "semantic_head": "包装",
        "support": "lexical_semantics",
        "basis": "包装是词法主词",
    }
    semantics["qualifiers"] = [
        {
            "term": "设备",
            "relation": "served_object",
            "target": "防护包装",
            "support": "lexical_semantics",
            "basis": "设备是防护包装的被服务对象",
        }
    ]

    validated = validate_content_world_root_against_semantics(exploration, semantics)

    assert validated["content_world_root"]["term"] == "防护包装"
    assert validated["content_world_root"]["purpose_world_checks"][0]["decision"] == "keep_product_root"


def test_modifier_contract_does_not_ask_the_model_to_repeat_a_derived_decision():
    prompt = CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT

    assert '"decision":' not in prompt
    assert "三项反事实结果唯一推导" in prompt
    assert "`promote_to_root` 时它成为根" in prompt
    assert "`keep_product_root` 时它保留" in prompt


def test_exploration_parser_requires_all_comparative_scopes_without_forcing_connections():
    payload = _valid_exploration()
    payload["comparative_scope_checks"][2] = {
        "scope": "ethnic_and_cultural_groups",
        "status": "not_structurally_connected",
        "direction": None,
        "basis": "该专业任务与民族或文化习惯没有直接结构关系",
    }
    parsed = parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    assert parsed["comparative_scope_checks"][2]["direction"] is None

    payload["comparative_scope_checks"].pop()
    try:
        parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    except ValueError as exc:
        assert "comparative_scope_checks" in str(exc)
    else:
        raise AssertionError("a comparative scope was silently skipped")


def test_projected_map_preserves_one_root_without_competing_subworld_routes():
    projected = project_content_world_map(
        _valid_semantics(),
        _parsed_exploration(),
        grounded_user_statements=["用户逐字原话"],
    )

    assert projected["root_subject"] == "品类"
    assert projected["commercial_object"] == "属性品类"
    assert projected["root_world"]["types_and_subworlds"] == _valid_exploration()["downward_expansion"]
    assert projected["root_world"]["time_and_history"] == ["形成、历史变化与未来走向"]
    assert projected["root_world"]["geography_and_environment"] == ["不同地域和环境中的差异"]
    assert projected["root_world"]["culture_and_habits"] == ["不同地方如何理解、使用并形成生活习惯"]
    assert projected["root_world"]["cross_cultural_comparison"] == [
        {
            "scope": item["scope"],
            "direction": item["direction"],
            "basis": item["basis"],
        }
        for item in _valid_exploration()["comparative_scope_checks"]
    ]
    assert projected["root_world"]["cross_domain_research"] == _valid_exploration()["cross_domain_connections"]
    assert projected["upward_connections"] == _valid_exploration()["upward_expansion"]
    assert projected["root_relation"] == {
        "term": "品类",
        "relation_to_commercial_object": "属性品类本身就是一个可持续展开的完整对象世界",
        "selection_basis": "保留已有容量的具体品类，不用泛化概念替换",
        "modifier_handling": [
            {
                "term": "属性",
                "decision": "branch_lens",
                "without_modifier_root": "品类",
            }
        ],
    }
    assert "basis" not in projected["root_relation"]["modifier_handling"][0]
    assert "constitutive_function_preserved" not in projected["root_relation"]["modifier_handling"][0]
    assert "subworld_lenses" not in projected
    assert "candidate_worlds" not in projected
    assert "seller_evidence" not in projected
    assert "downstream_unknowns" not in projected
    assert projected["coverage_contract"] == [
        {"axis": "types_and_subworlds", "label": "种类与子世界"},
        {"axis": "time_and_history", "label": "时间与历史"},
        {"axis": "geography_and_environment", "label": "地理与环境"},
        {"axis": "culture_and_habits", "label": "文化与生活习惯"},
        {"axis": "cross_cultural_comparison", "label": "跨国家、地区与文化群体"},
        {"axis": "people", "label": "人物"},
        {"axis": "events", "label": "事件"},
        {"axis": "conflicts", "label": "冲突"},
        {"axis": "cross_domain_research", "label": "跨领域待研究连接"},
    ]
    assert projected["fact_boundary"] == {
        "allowed_subject_claims": ["用户逐字原话"],
        "do_not_infer": [
            "不得把简称或大类补成用户未陈述的具体事实、现场、素材或能力。",
            "不得把‘或’连接的未决选项写成同时具备。",
            "一般知识和待研究连接只说明这个世界可以研究什么，不证明主体亲历、掌握或拥有。",
        ],
    }
    assert projected["research_boundary"] == "地图节点均为待研究的内容方向；发布前核验，不作为主体事实或已核验外部事实。"
    assert projected["insufficiency"] is None
    assert list(projected)[-1] == "response_contract"
    assert projected["response_contract"] == {
        "answer_mode": "current_content_world_judgment",
        "answer_scope": "只回答当前根主语与内容世界判断；说完必报轴与研究边界后立即停止。",
        "output_shape": [
            "根主语及其与商业对象的关系",
            "每个必报轴及其为什么属于这个内容世界",
            "一句研究与主体事实边界",
        ],
        "stop_rule": "完成 output_shape 第三项后立即结束；不追加未知清单、下一步、追问、定位、形式或其他模块事项。",
        "final_line_rule": "研究与主体事实边界必须是最后一段；其后不得再有文字，不得以问句结尾。",
        "required_axis_labels": [
            "种类与子世界",
            "时间与历史",
            "地理与环境",
            "文化与生活习惯",
            "跨国家、地区与文化群体",
            "人物",
            "事件",
            "冲突",
            "跨领域待研究连接",
        ],
        "allowed_subject_claims": ["用户逐字原话"],
        "must_not": [
            "本轮不展开其他业务模块，也不借边界说明补写其内容。",
            "本轮不询问追问问题；不得因模块外信息转成问卷。",
            "不得把未定义简称补成用户没有陈述的具体事实。",
            "不得把源头、生产者或专业身份补成具体场地、亲历、素材、能力或成果。",
            "不得把‘或’连接的未决选项写成同时具备。",
            "不得把地图中的一般知识或待研究方向写成主体事实或已核验事实。",
        ],
        "unknown_wording": "本轮不提及模块外信息；它们不影响当前内容世界边界。",
    }

    serialized_contract = json.dumps(projected["response_contract"], ensure_ascii=False)
    for out_of_scope_term in ("卖货", "广告", "变现", "成交", "转化", "客单", "复购", "带货"):
        assert out_of_scope_term not in serialized_contract


def test_projection_can_root_an_enabling_product_in_the_named_activity_it_serves():
    semantics = _valid_semantics()
    semantics["offer_object"] = {
        "term": "重庆火锅底料",
        "semantic_head": "底料",
        "support": "lexical_semantics",
        "basis": "底料决定组合表达的词法品类",
    }
    semantics["qualifiers"] = [
        {
            "term": "重庆",
            "relation": "location_or_channel",
            "target": "火锅",
            "support": "lexical_semantics",
            "basis": "重庆修饰火锅的地域与风味",
        },
        {
            "term": "火锅",
            "relation": "purpose",
            "target": "底料",
            "support": "lexical_semantics",
            "basis": "底料直接用于制作火锅",
        },
    ]
    exploration = _valid_exploration()
    exploration["content_world_root"] = {
        "term": "火锅",
        "relation_to_commercial_object": "底料是实现火锅风味和烹饪的核心商品载体，火锅是它直接服务的完整活动世界",
        "selection_basis": "商业表达已明示火锅；它比底料更有横向容量，且能直接归因回底料",
        "purpose_world_checks": [
            {
                "term": "火锅",
                "product_role": "intermediate_enabler",
                "world_complete": True,
                "capacity_relation": "broader",
                "return_path": "火锅世界可通过锅底风味与底料的实现环节回到商品",
                "basis": "火锅包含底料的原料、制作与使用分支，还有底料没有的时空、食用者、社交仪式和文化容量",
            }
        ],
        "modifier_handling": [
            {
                "term": "重庆",
                "without_modifier_root": "火锅",
                "complete_without_modifier": True,
                "constitutive_function_preserved": True,
                "return_path": "火锅世界可通过重庆风味与底料分支回到商品",
                "basis": "重庆是火锅的地域与风味分支，不取代火锅世界",
            }
        ],
    }

    parsed_exploration = parse_content_world_exploration(json.dumps(exploration, ensure_ascii=False))
    projected = project_content_world_map(
        semantics,
        parsed_exploration,
        grounded_user_statements=["我是卖重庆火锅底料的"],
    )

    assert projected["commercial_object"] == "重庆火锅底料"
    assert projected["lexical_head"] == "底料"
    assert projected["root_subject"] == "火锅"
    assert projected["root_subject"] != semantics["offer_object"]["semantic_head"]
    assert projected["root_subject"] != "重庆"
    assert "直接服务" in projected["root_relation"]["relation_to_commercial_object"]
    assert projected["root_relation"]["modifier_handling"] == [
        {
            "term": "重庆",
            "decision": "branch_lens",
            "without_modifier_root": "火锅",
        }
    ]


def test_explorer_tool_schema_has_no_model_supplied_fact_argument():
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=True,
        reasoning_effort="high",
        app_config=SimpleNamespace(),
    )

    schema = convert_to_openai_tool(tool)["function"]
    assert schema["name"] == "explore_content_worlds"
    assert schema["parameters"]["properties"] == {}


def test_explorer_reads_only_user_authored_thread_text_and_preserves_original_content(monkeypatch):
    model = FakeModel(
        [
            AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False)),
            AIMessage(content=json.dumps(_valid_exploration(), ensure_ascii=False)),
        ]
    )
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )
    runtime = _runtime(
        messages=[
            HumanMessage(
                content="--- BEGIN USER INPUT ---\n模型可见包装\n--- END USER INPUT ---",
                additional_kwargs={ORIGINAL_USER_CONTENT_KEY: "用户真正说的业务事实"},
            ),
            AIMessage(content="助手擅自补造的客户、渠道和现场"),
            HumanMessage(content="隐藏注入", additional_kwargs={"hide_from_ui": True}),
        ]
    )

    result = json.loads(asyncio.run(tool.coroutine(runtime=runtime)))

    assert result["status"] == "ok"
    first_model_input = "\n".join(str(message.content) for message in model.calls[0][0])
    assert "用户真正说的业务事实" in first_model_input
    assert "模型可见包装" not in first_model_input
    assert "助手擅自补造" not in first_model_input
    assert "隐藏注入" not in first_model_input


def test_explorer_is_not_a_global_or_subagent_builtin():
    from deerflow.tools.tools import BUILTIN_TOOLS, SUBAGENT_TOOLS

    globally_registered_names = {tool.name for tool in [*BUILTIN_TOOLS, *SUBAGENT_TOOLS]}
    assert "explore_content_worlds" not in globally_registered_names


def test_explorer_uses_two_bounded_model_calls_and_hides_private_reasoning(monkeypatch):
    journal = MagicMock()
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(_valid_semantics(), ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_SEMANTIC_REASONING"},
                response_metadata={"model_name": "provider-model"},
                usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            ),
            AIMessage(
                content=json.dumps(_valid_exploration(), ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_WORLD_REASONING"},
                response_metadata={"model_name": "provider-model"},
                usage_metadata={"input_tokens": 200, "output_tokens": 40, "total_tokens": 240},
            ),
        ]
    )
    create_model = MagicMock(return_value=model)
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        create_model,
    )
    app_config = SimpleNamespace()
    tool = build_content_world_explorer_tool(
        model_name="resolved-lead-model",
        thinking_enabled=True,
        reasoning_effort="high",
        app_config=app_config,
    )

    raw = asyncio.run(
        tool.coroutine(
            runtime=_runtime(
                journal=journal,
                messages=[HumanMessage(content="主体从事一种组合品类的生产，想做账号")],
            ),
        )
    )
    result = json.loads(raw)

    assert result == {
        "status": "ok",
        "grounded_user_statements": ["主体从事一种组合品类的生产，想做账号"],
        "content_world_map": project_content_world_map(
            _valid_semantics(),
            _parsed_exploration(),
            grounded_user_statements=["主体从事一种组合品类的生产，想做账号"],
        ),
    }
    assert "business_semantics" not in result
    assert "PRIVATE_SEMANTIC_REASONING" not in raw
    assert "PRIVATE_WORLD_REASONING" not in raw
    assert len(model.calls) == 2
    assert model.calls[0][1]["run_name"] == "content_world_semantics"
    assert model.calls[1][1]["run_name"] == "content_world_exploration"
    for _, config in model.calls:
        assert config["callbacks"] == []
        assert TAG_NOSTREAM in config["tags"]
    create_model.assert_called_once_with(
        name="resolved-lead-model",
        thinking_enabled=True,
        reasoning_effort="high",
        app_config=app_config,
        attach_tracing=False,
    )
    assert journal.record_external_llm_usage_records.call_count == 2
    callers = [call.args[0][0]["caller"] for call in journal.record_external_llm_usage_records.call_args_list]
    assert callers == ["tool:content-world:semantics", "tool:content-world:exploration"]


def test_explorer_repairs_one_invalid_exploration_contract_without_leaking_it(monkeypatch):
    invalid_exploration = _valid_exploration()
    invalid_exploration.pop("culture_and_habits", None)
    invalid_exploration["horizontal_expansion"].pop("culture_and_habits")
    invalid_text = json.dumps(invalid_exploration, ensure_ascii=False)
    model = FakeModel(
        [
            AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False)),
            AIMessage(content=invalid_text),
            AIMessage(content=json.dumps(_valid_exploration(), ensure_ascii=False)),
        ]
    )
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    raw = asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="待探索业务")])))
    result = json.loads(raw)

    assert result["status"] == "ok"
    assert len(model.calls) == 3
    repair_messages = model.calls[2][0]
    assert invalid_text in [message.content for message in repair_messages]
    assert "只修正 JSON" in repair_messages[-1].content
    assert "horizontal_expansion has invalid fields" in repair_messages[-1].content
    assert invalid_text not in raw


def test_explorer_repairs_a_semantically_inconsistent_attribute_root(monkeypatch):
    invalid_exploration = _valid_exploration()
    invalid_exploration["content_world_root"]["term"] = "属性品类"
    invalid_exploration["content_world_root"]["modifier_handling"][0]["constitutive_function_preserved"] = False
    invalid_text = json.dumps(invalid_exploration, ensure_ascii=False)
    model = FakeModel(
        [
            AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False)),
            AIMessage(content=invalid_text),
            AIMessage(content=json.dumps(_valid_exploration(), ensure_ascii=False)),
        ]
    )
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    result = json.loads(asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="待探索业务")]))))

    assert result["status"] == "ok"
    assert result["content_world_map"]["root_subject"] == "品类"
    assert len(model.calls) == 3
    assert "attribute-like qualifier" in model.calls[2][0][-1].content
    assert "rebuild every expansion axis" in model.calls[2][0][-1].content


def test_explorer_repairs_one_invalid_semantic_contract_before_exploring(monkeypatch):
    invalid_semantics = _valid_semantics()
    invalid_semantics.pop("ambiguities")
    invalid_text = json.dumps(invalid_semantics, ensure_ascii=False)
    model = FakeModel(
        [
            AIMessage(content=invalid_text),
            AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False)),
            AIMessage(content=json.dumps(_valid_exploration(), ensure_ascii=False)),
        ]
    )
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    result = json.loads(asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="待探索业务")]))))

    assert result["status"] == "ok"
    assert len(model.calls) == 3
    assert invalid_text in [message.content for message in model.calls[1][0]]


def test_explorer_stops_after_one_failed_contract_repair(monkeypatch):
    invalid = AIMessage(content='{"wrong": true}')
    model = FakeModel(
        [
            AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False)),
            invalid,
            invalid,
        ]
    )
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    result = json.loads(asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="待探索业务")]))))

    assert result == {
        "status": "error",
        "error_code": "invalid_model_output",
        "message": "内容世界探索结果无效；请依据用户原话继续当前判断。",
    }
    assert len(model.calls) == 3


def test_empty_exploration_projects_every_explicit_world_axis(monkeypatch):
    semantics = _valid_semantics()
    semantics["offer_object"] = None
    semantics["insufficiency"] = "没有商业对象"
    model = FakeModel([AIMessage(content=json.dumps(semantics, ensure_ascii=False))])
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    result = json.loads(asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="我只有一个身份标签，想做账号")]))))

    assert result["content_world_map"]["root_world"] == {
        "types_and_subworlds": [],
        "time_and_history": [],
        "geography_and_environment": [],
        "culture_and_habits": [],
        "people": [],
        "events": [],
        "conflicts": [],
        "cross_domain_research": [],
        "cross_cultural_comparison": [],
    }
    assert result["content_world_map"]["coverage_contract"] == []
    assert result["content_world_map"]["response_contract"]["answer_mode"] == "ask_one_object_question"
    assert result["content_world_map"]["response_contract"]["required_axis_labels"] == []


def test_projected_handoff_leads_with_fact_closure_before_creative_axes():
    projected = project_content_world_map(
        _valid_semantics(),
        _valid_exploration(),
        grounded_user_statements=["用户真正说的话"],
    )

    assert list(projected)[:2] == ["fact_boundary", "root_subject"]
    assert projected["fact_boundary"]["allowed_subject_claims"] == ["用户真正说的话"]
    assert projected["fact_boundary"]["do_not_infer"] == [
        "不得把简称或大类补成用户未陈述的具体事实、现场、素材或能力。",
        "不得把‘或’连接的未决选项写成同时具备。",
        "一般知识和待研究连接只说明这个世界可以研究什么，不证明主体亲历、掌握或拥有。",
    ]
    assert "subject_facts" not in projected["fact_boundary"]
    assert list(projected)[-1] == "response_contract"


def test_explorer_prompt_keeps_generated_nodes_at_research_direction_granularity():
    prompt = CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT

    assert "只写类别级研究方向" in prompt
    assert "具体命名实体" in prompt
    assert "除非名称来自用户原话" in prompt
    assert "标准编号" in prompt
    assert "只写成待核验的研究问题" in prompt
    assert "均不得声称已经核验" in prompt


def test_explorer_returns_a_redacted_error_when_the_second_call_fails(monkeypatch):
    model = SecondCallFailureModel([AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False))])
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    raw = asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="待探索业务")])))
    result = json.loads(raw)

    assert result == {
        "status": "error",
        "error_code": "provider_error",
        "message": "内容世界探索暂时不可用；请依据用户原话继续当前判断。",
    }
    assert "PRIVATE_CREDENTIAL_MARKER" not in raw
