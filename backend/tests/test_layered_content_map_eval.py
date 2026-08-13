from __future__ import annotations

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from scripts.run_layered_content_map_eval import (
    LAYERED_CONTENT_MAP_SYSTEM_PROMPT,
    build_layered_map_messages,
    calculate_live_call_count,
    calculate_provider_call_budget,
    default_layered_cases,
    parse_layered_content_map,
    run_layered_map_case,
    validate_layered_map_against_case,
)


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def _case(case_id: str):
    return next(case for case in default_layered_cases() if case.case_id == case_id)


def _valid_map() -> dict[str, object]:
    return {
        "source_object": {
            "term": "原始对象",
            "basis": "用户明确说明该业务对象",
            "evidence_refs": ["business-1"],
        },
        "audience_world": {
            "term": "完整世界",
            "relation_to_source": "same_object_world",
            "selection_basis": "该对象本身已能长期展开",
            "source_relation": "观众世界与原始对象直接重合",
            "evidence_refs": ["business-1"],
            "support": "inferred",
        },
        "content_engines": [
            {
                "id": "engine-1",
                "subject": "对象知识与故事",
                "content_function": "story_and_culture",
                "basis": "完整世界内部可反复生长",
                "evidence_refs": ["business-1"],
                "support": "inferred",
            }
        ],
        "attention_entries": [
            {
                "id": "attention-1",
                "carrier": "普通人熟悉的问题",
                "mechanism": "降低进入门槛",
                "basis": "从观众日常问题进入完整世界",
                "evidence_refs": ["business-1"],
                "support": "inferred",
            }
        ],
        "expansion_nodes": [
            {
                "id": "node-1",
                "parent_type": "audience_world",
                "parent_id": "audience_world",
                "axis": "time_and_history",
                "direction": "该对象如何随时间变化",
                "connection": "时间变化会改变该世界的形态与意义",
                "evidence_refs": ["business-1"],
                "support": "research_hypothesis",
                "research_needed": True,
            }
        ],
        "unknowns": ["具体史实需另行核验"],
        "insufficiency": None,
    }


def test_prompt_combines_four_layers_with_sparse_rooted_expansion():
    prompt = LAYERED_CONTENT_MAP_SYSTEM_PROMPT

    for required in (
        "原始业务对象",
        "观众内容世界",
        "内容发动机",
        "注意力入口",
        "稀疏展开节点",
        "去经营容器反事实",
        "去修饰条件反事实",
        "去发动机反事实",
        "一个简短名词或活动名称",
        "保留完整商品表达中属于商品本身的地域、材质、用途或被服务对象",
        "被选择、购买、烹饪、食用或使用",
        "独立的参与者、规则、事件和冲突",
        "不得以稀疏为由省略",
        "八个轴都在内部扫描一遍",
        "展开节点必须挂回",
        "不机械凑齐",
    ):
        assert required in prompt
    assert "内容是讲什么" in prompt
    assert "表现形式是怎么呈现" in prompt
    assert "不是强制检查表" in prompt
    for out_of_scope_term in ("卖货", "销售", "广告", "变现", "成交", "转化", "客单", "复购", "带货"):
        assert out_of_scope_term not in prompt
    for leaked_gold in ("黄金礼品", "水果店", "海鲜", "火锅底料", "腕表", "医美"):
        assert leaked_gold not in prompt


def test_six_reviewed_cases_are_present_and_gold_is_not_model_visible():
    cases = default_layered_cases()
    assert [case.case_id for case in cases] == [
        "gold-gift",
        "fruit-shop",
        "seafood-source",
        "chongqing-hotpot-base",
        "watch-account",
        "medical-aesthetics-account",
    ]

    for case in cases:
        messages = build_layered_map_messages(case=case)
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        payload = json.loads(messages[1].content)
        assert "acceptance" not in payload
        assert "expected_world_terms" not in payload
        assert "expected_source_terms" not in payload
        assert "forbidden_world_terms" not in payload


def test_parser_accepts_sparse_expansion_and_rejects_contract_drift():
    payload = _valid_map()
    assert parse_layered_content_map(json.dumps(payload, ensure_ascii=False)) == payload

    payload["expansion_nodes"] = []
    assert parse_layered_content_map(json.dumps(payload, ensure_ascii=False)) == payload

    payload["unexpected"] = []
    with pytest.raises(ValueError, match="exactly"):
        parse_layered_content_map(json.dumps(payload, ensure_ascii=False))


def test_parser_reports_nested_missing_and_extra_fields_for_bounded_repair():
    payload = _valid_map()
    payload["attention_entries"][0].pop("mechanism")
    payload["attention_entries"][0]["entry_type"] = "question"

    with pytest.raises(ValueError) as exc_info:
        parse_layered_content_map(json.dumps(payload, ensure_ascii=False))

    message = str(exc_info.value)
    assert "attention_entries[0]" in message
    assert "missing: mechanism" in message
    assert "extra: entry_type" in message


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value["expansion_nodes"][0].update({"parent_type": "content_engine", "parent_id": "missing"}),
            "missing",
        ),
        (lambda value: value["expansion_nodes"][0].update({"research_needed": False}), "research_needed"),
        (lambda value: value["expansion_nodes"][0].update({"axis": "sales"}), "axis"),
    ],
)
def test_parser_rejects_unrooted_or_unverified_expansion(mutate, error):
    payload = _valid_map()
    mutate(payload)

    with pytest.raises(ValueError, match=error):
        parse_layered_content_map(json.dumps(payload, ensure_ascii=False))


def test_validation_uses_review_labels_after_inference_not_keyword_rules():
    payload = _valid_map()
    payload["source_object"]["term"] = "广告业务"
    payload["source_object"]["basis"] = "这就是用户明确陈述的业务对象"
    validate_layered_map_against_case(payload, case=None)

    hotpot = _case("chongqing-hotpot-base")
    wrong = _valid_map()
    wrong["source_object"]["term"] = "重庆火锅底料"
    wrong["audience_world"]["term"] = "重庆火锅"
    with pytest.raises(ValueError, match="audience_world"):
        validate_layered_map_against_case(wrong, case=hotpot)


def test_case_evidence_separates_user_labels_from_real_account_observations():
    cases = default_layered_cases()
    by_id = {case.case_id: case for case in cases}

    for case_id in ("gold-gift", "fruit-shop", "seafood-source", "chongqing-hotpot-base"):
        assert by_id[case_id].review_status == "user_corrected_gold"
    for case_id in ("watch-account", "medical-aesthetics-account"):
        assert by_id[case_id].review_status == "reviewed_real_account"
        assert any(item.kind == "platform_observation" for item in by_id[case_id].evidence)


def test_live_call_budgets_are_explicit_and_have_no_judge():
    assert calculate_live_call_count(case_count=6, model_count=1) == 6
    assert calculate_provider_call_budget(primary_calls=6, max_repair_calls=1) == 7


def test_run_hashes_reasoning_and_allows_one_schema_repair():
    case = _case("fruit-shop")
    payload = _valid_map()
    payload["source_object"]["term"] = "水果"
    payload["audience_world"]["term"] = "水果"
    invalid = {**payload, "commentary": "remove"}
    model = FakeModel(
        [
            AIMessage(content=json.dumps(invalid, ensure_ascii=False), additional_kwargs={"reasoning_content": "PRIVATE"}),
            AIMessage(content=json.dumps(payload, ensure_ascii=False)),
        ]
    )

    result = asyncio.run(run_layered_map_case(model=model, model_name="test", case=case, max_repair_calls=1))

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["repair_calls"] == 1
    assert result["layered_content_map"] == payload
    assert result["provider_reasoning_present"] is True
    assert "PRIVATE" not in serialized
    assert "remove" not in serialized
    assert len(model.calls) == 2
    assert "不要重新做内容判断" in model.calls[1][-1].content


def test_run_returns_a_redacted_failure_record_after_contract_budget_is_exhausted():
    case = _case("fruit-shop")
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps({"wrong": "PRIVATE_VISIBLE_OUTPUT"}, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_REASONING"},
            )
        ]
    )

    result = asyncio.run(run_layered_map_case(model=model, model_name="test", case=case))

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["layered_content_map"] is None
    assert result["automatic_review"]["status"] == "failed_contract"
    assert result["automatic_review"]["errors"] == ["layered content map must contain exactly the configured fields"]
    assert result["provider_calls"] == 1
    assert result["repair_calls"] == 0
    assert result["provider_reasoning_present"] is True
    assert "PRIVATE_VISIBLE_OUTPUT" not in serialized
    assert "PRIVATE_REASONING" not in serialized
