from __future__ import annotations

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from scripts.run_account_content_structure_eval import (
    ACCOUNT_CONTENT_STRUCTURE_SYSTEM_PROMPT,
    build_structure_messages,
    calculate_live_call_count,
    calculate_provider_call_budget,
    default_structure_cases,
    parse_account_content_structure,
    run_structure_case,
    validate_structure_against_case,
)


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def _case(case_id: str):
    return next(case for case in default_structure_cases() if case.case_id == case_id)


def _valid_structure() -> dict[str, object]:
    return {
        "source_object": {
            "term": "原始业务对象",
            "basis": "用户明确说明主体从事该对象",
            "evidence_refs": ["business-1"],
        },
        "audience_world": {
            "term": "长期主题世界",
            "relation_to_source": "use_or_activity_world",
            "selection_basis": "该世界能容纳多个长期内容发动机",
            "engine_boundary": "移除具体方法后，长期主题世界仍完整",
            "population_boundary": "没有覆盖证据，不在世界名称中限定人群",
            "source_relation": "原始业务对象是该主题世界中的一种相关对象或方法",
            "evidence_refs": ["observation-1"],
            "support": "inferred",
        },
        "content_engines": [
            {
                "id": "engine-1",
                "subject": "日常方法",
                "content_function": "practical_help",
                "basis": "可见内容持续解释普通人可执行的方法",
                "evidence_refs": ["observation-1"],
                "support": "observed",
            }
        ],
        "attention_entries": [
            {
                "id": "attention-1",
                "carrier": "公众熟悉的人物类别",
                "mechanism": "借共同认知降低陌生话题的进入门槛",
                "basis": "用户观察到内容使用了这类入口",
                "evidence_refs": ["observation-1"],
                "support": "observed",
            }
        ],
        "unknowns": ["实际受众覆盖未知"],
        "insufficiency": None,
    }


def test_prompt_separates_source_world_engines_and_attention_without_selling():
    prompt = ACCOUNT_CONTENT_STRUCTURE_SYSTEM_PROMPT

    for required in (
        "原始业务对象",
        "观众内容世界",
        "内容发动机",
        "注意力入口",
        "最小完整观众根",
        "去发动机反事实",
        "谁在看",
    ):
        assert required in prompt
    assert "不是最终起号方案" in prompt
    assert "内容是讲什么" in prompt
    assert "表现形式是怎么呈现" in prompt
    assert "只输出上述四层内容结构" in prompt
    assert "不得设计信任结构、人设或受众画像" in prompt
    for out_of_scope_term in ("卖货", "销售", "广告", "变现", "成交", "转化", "客单", "复购", "带货"):
        assert out_of_scope_term not in prompt
    assert "怎么卖" not in prompt
    assert "B/C" not in prompt
    for leaked_case in ("腕表", "医美", "明星", "林志玲", "防晒", "喷雾"):
        assert leaked_case not in prompt


def test_prompt_keeps_object_worlds_and_separates_engines_from_the_root():
    prompt = ACCOUNT_CONTENT_STRUCTURE_SYSTEM_PROMPT

    assert "原始业务对象本身已经是完整且有长期容量的世界" in prompt
    assert "观众内容世界可以与原始业务对象相同" in prompt
    assert "泛化的生活方式、情绪价值或人性" in prompt
    assert "知识、故事、判断、方法" in prompt
    assert "不得拼进" in prompt
    assert "A 与 B" in prompt
    assert "包含另一个成分" in prompt
    assert "只保留较大的完整世界" in prompt
    assert "人群标签不得进入" in prompt
    assert "注意力入口不能反过来冒充观众内容世界" in prompt


def test_structure_messages_keep_evidence_untrusted_and_hide_review_expectations():
    case = _case("medical-aesthetics-account")
    messages = build_structure_messages(case=case)

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    payload = json.loads(messages[1].content)
    assert payload["case_id"] == case.case_id
    assert payload["business_expression"] == case.business_expression
    assert payload["evidence"]
    assert "review_expectations" not in payload
    assert messages[1].additional_kwargs["original_user_content"] == case.business_expression


def test_parse_structure_accepts_variable_nodes_and_no_attention_entries():
    payload = _valid_structure()
    assert parse_account_content_structure(json.dumps(payload, ensure_ascii=False)) == payload

    payload["attention_entries"] = []
    assert parse_account_content_structure(json.dumps(payload, ensure_ascii=False)) == payload


def test_contract_has_no_trust_commerce_offer_or_conversion_fields():
    payload = _valid_structure()
    serialized = json.dumps(payload, ensure_ascii=False)

    for forbidden in (
        "trust_bridges",
        "commercial_anchor",
        "commercial_bridges",
        "routes",
        "offer",
        "availability",
        "conversion",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda value: value.update({"extra": []}), "exactly"),
        (
            lambda value: value["audience_world"].update({"relation_to_source": "generic_lifestyle"}),
            "relation_to_source",
        ),
        (
            lambda value: value["content_engines"][0].update({"support": "certain"}),
            "support",
        ),
        (
            lambda value: value["attention_entries"][0].update({"mechanism": ""}),
            "mechanism",
        ),
    ],
)
def test_parse_structure_rejects_contract_drift(mutate, error):
    payload = _valid_structure()
    mutate(payload)

    with pytest.raises(ValueError, match=error):
        parse_account_content_structure(json.dumps(payload, ensure_ascii=False))


def test_validation_rejects_unknown_evidence_references():
    case = _case("medical-aesthetics-account")
    payload = _valid_structure()
    payload["attention_entries"][0]["evidence_refs"] = ["missing-evidence"]

    with pytest.raises(ValueError, match="missing-evidence"):
        validate_structure_against_case(payload, case=case)


def test_validation_does_not_use_a_keyword_gate_for_a_legitimate_content_subject():
    case = _case("medical-aesthetics-account")
    payload = _valid_structure()
    payload["source_object"]["term"] = "广告业务"
    payload["source_object"]["basis"] = "用户业务对象本身就是广告业务"

    validate_structure_against_case(payload, case=case)


def test_default_cases_contain_content_evidence_but_no_selling_hypotheses():
    medical = _case("medical-aesthetics-account")
    watch = _case("watch-account")
    all_statements = "\n".join(item.statement for case in (medical, watch) for item in case.evidence)

    assert any("日常保养" in item.statement for item in medical.evidence)
    assert any("冷启动" in item.statement for item in watch.evidence)
    assert any("当前" in item.statement and "人物" in item.statement for item in watch.evidence)
    for forbidden in ("喷雾广告", "成交", "变现能力", "客单", "复购"):
        assert forbidden not in all_statements


def test_live_call_budgets_are_explicit_and_have_no_judge():
    assert calculate_live_call_count(case_count=2, model_count=1) == 2
    assert calculate_provider_call_budget(primary_calls=2, max_repair_calls=1) == 3


def test_structure_case_persists_visible_output_and_reasoning_hash_only():
    case = _case("medical-aesthetics-account")
    payload = _valid_structure()
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(payload, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_REASONING"},
            )
        ]
    )

    result = asyncio.run(run_structure_case(model=model, model_name="test-model", case=case))

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["account_content_structure"] == payload
    assert result["provider_reasoning_present"] is True
    assert len(result["provider_reasoning_sha256"]) == 64
    assert "PRIVATE_REASONING" not in serialized
    assert len(model.calls) == 1


def test_structure_case_can_repair_json_once_without_reconsidering_content():
    case = _case("medical-aesthetics-account")
    payload = _valid_structure()
    model = FakeModel(
        [
            AIMessage(content=json.dumps({**payload, "commentary": "REMOVE_ME"}, ensure_ascii=False)),
            AIMessage(content=json.dumps(payload, ensure_ascii=False)),
        ]
    )

    result = asyncio.run(run_structure_case(model=model, model_name="test-model", case=case, max_repair_calls=1))

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["account_content_structure"] == payload
    assert result["repair_calls"] == 1
    assert result["provider_calls"] == 2
    assert "REMOVE_ME" not in serialized
    assert isinstance(model.calls[1][-1], HumanMessage)
    assert "只修复 JSON 契约" in model.calls[1][-1].content
    assert "不要重新做内容判断" in model.calls[1][-1].content


def test_structure_case_does_not_spend_an_unapproved_repair_call():
    case = _case("medical-aesthetics-account")
    payload = _valid_structure()
    model = FakeModel([AIMessage(content=json.dumps({**payload, "extra": True}, ensure_ascii=False))])

    with pytest.raises(ValueError, match="exactly"):
        asyncio.run(run_structure_case(model=model, model_name="test-model", case=case))

    assert len(model.calls) == 1
