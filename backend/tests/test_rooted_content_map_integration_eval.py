from __future__ import annotations

import asyncio
import json
from argparse import Namespace
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from scripts.run_rooted_content_map_integration_eval import (
    FROZEN_MODEL,
    ROOTED_CONTENT_MAP_SYSTEM_PROMPT,
    build_integration_messages,
    calculate_primary_call_count,
    calculate_provider_call_budget,
    default_integration_cases,
    parse_rooted_content_map,
    run_evaluation,
    run_integration_case,
)


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def _case(case_id: str):
    return next(case for case in default_integration_cases() if case.case_id == case_id)


def _valid_payload() -> dict[str, object]:
    return {
        "source_object": {
            "term": "原始对象",
            "basis": "用户明确提供该对象",
            "evidence_refs": ["business-1"],
        },
        "root_candidates": [
            {
                "id": "object-root",
                "term": "完整对象",
                "relation_to_source": "same_object",
                "derivation": "移除经营容器后保留完整对象",
                "capacity_examples": ["不同子类型如何形成各自的对象世界", "该对象在不同历史阶段如何变化"],
                "business_return_path": "具体对象内容可以自然回到来源业务",
                "overreach_risk": "可能停在产品目录",
                "evidence_refs": ["business-1"],
            },
            {
                "id": "activity-root",
                "term": "相关活动",
                "relation_to_source": "use_or_activity",
                "derivation": "比较该对象直接服务的活动",
                "capacity_examples": ["活动中的人物关系与规则如何变化"],
                "business_return_path": "活动需要来源对象参与",
                "overreach_risk": "普通使用动作可能抢走完整对象",
                "evidence_refs": ["business-1"],
            },
        ],
        "selected_content_world": {
            "candidate_id": "object-root",
            "reason": "完整对象具有更大的有效容量且保持业务特异性",
        },
        "content_map_nodes": [
            {
                "id": "node-types",
                "parent_candidate_id": "object-root",
                "axis": "types_and_subworlds",
                "direction": "不同子类型各自包含什么结构、用途和争议",
                "connection": "子类型直接构成完整对象世界",
                "evidence_refs": ["business-1"],
                "support": "research_hypothesis",
                "research_needed": True,
            },
            {
                "id": "node-history",
                "parent_candidate_id": "object-root",
                "axis": "time_and_history",
                "direction": "该对象在不同时代的形态、规则与意义如何变化",
                "connection": "历史变化会改变对象本身",
                "evidence_refs": ["business-1"],
                "support": "research_hypothesis",
                "research_needed": True,
            },
        ],
        "unknowns": ["具体事实需要后续研究核验"],
    }


def test_prompt_uses_content_capacity_to_choose_one_root_without_need_bias():
    prompt = ROOTED_CONTENT_MAP_SYSTEM_PROMPT

    for required in (
        "语义迁移不是向上升级",
        "没有天然优先级",
        "最大有效内容世界",
        "完整对象可以胜出",
        "实际内容方向",
        "轴名称本身不是内容地图节点",
        "所有地图节点必须挂在最终选中的同一个根上",
        "内容是讲什么，表现形式是怎么呈现",
    ):
        assert required in prompt
    for leaked_gold in ("黄金礼品", "水果店", "海鲜", "火锅底料", "腕表", "医美"):
        assert leaked_gold not in prompt
    for forbidden in ("固定三个", "至少三个候选", "70%", "10天", "3类各2条"):
        assert forbidden not in prompt


def test_four_user_reviewed_cases_are_present_but_gold_never_enters_messages():
    cases = default_integration_cases()
    assert [case.case_id for case in cases] == [
        "fruit-shop",
        "gold-gift",
        "seafood-source",
        "chongqing-hotpot-base",
    ]
    assert all(case.review_status == "user_corrected_gold" for case in cases)

    for case in cases:
        messages = build_integration_messages(case=case)
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        payload = json.loads(messages[1].content)
        for hidden in ("acceptance", "review_expectations", "world_terms", "required_axes", "forbidden_world_terms"):
            assert hidden not in payload


def test_parser_binds_selected_root_and_requires_actual_rooted_nodes():
    parsed = parse_rooted_content_map(
        json.dumps(_valid_payload(), ensure_ascii=False),
        allowed_evidence_ids={"business-1"},
    )

    assert parsed["selected_content_world"]["term"] == "完整对象"
    assert parsed["selected_content_world"]["relation_to_source"] == "same_object"
    assert {node["axis"] for node in parsed["content_map_nodes"]} == {
        "types_and_subworlds",
        "time_and_history",
    }
    assert all(node["parent_candidate_id"] == "object-root" for node in parsed["content_map_nodes"])


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda payload: payload["selected_content_world"].update({"candidate_id": "missing"}),
            "known candidate",
        ),
        (
            lambda payload: payload["content_map_nodes"][0].update({"parent_candidate_id": "activity-root"}),
            "selected content world",
        ),
        (lambda payload: payload["content_map_nodes"][0].update({"axis": "sales"}), "axis"),
        (
            lambda payload: payload["content_map_nodes"][0].update({"research_needed": False}),
            "research_needed",
        ),
        (lambda payload: payload["root_candidates"][0].update({"score": 90}), "root_candidates"),
        (lambda payload: payload["root_candidates"][0].update({"capacity_examples": []}), "capacity_examples"),
        (
            lambda payload: payload["source_object"].update({"evidence_refs": ["hidden-gold"]}),
            "unknown evidence",
        ),
    ],
)
def test_parser_rejects_unbound_maps_scores_empty_capacity_and_hidden_evidence(mutate, error):
    payload = _valid_payload()
    mutate(payload)

    with pytest.raises(ValueError, match=error):
        parse_rooted_content_map(
            json.dumps(payload, ensure_ascii=False),
            allowed_evidence_ids={"business-1"},
        )


def test_call_budget_is_one_primary_per_case_plus_one_shared_schema_repair():
    assert calculate_primary_call_count(case_count=4, model_count=1) == 4
    assert calculate_provider_call_budget(primary_calls=4, max_repair_calls=1) == 5


def test_run_hashes_reasoning_and_uses_schema_only_repair():
    valid = _valid_payload()
    invalid = {**valid, "commentary": "remove"}
    model = FakeModel(
        [
            AIMessage(content=json.dumps(invalid, ensure_ascii=False), additional_kwargs={"reasoning_content": "PRIVATE"}),
            AIMessage(content=json.dumps(valid, ensure_ascii=False)),
        ]
    )

    result = asyncio.run(
        run_integration_case(
            model=model,
            model_name="test",
            case=_case("fruit-shop"),
            max_repair_calls=1,
        )
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["contract_status"] == "passed"
    assert result["repair_calls"] == 1
    assert result["rooted_content_map"] is not None
    assert result["provider_reasoning_present"] is True
    assert "PRIVATE" not in serialized
    assert "remove" not in serialized
    assert len(model.calls) == 2
    assert "不要重新做业务判断" in model.calls[1][-1].content


def test_live_runner_rejects_non_frozen_model_before_provider_access(tmp_path: Path):
    args = Namespace(
        execute=True,
        models=["unfrozen-model"],
        case_ids=[],
        max_calls=4,
        max_repair_calls=1,
        seed=80,
        output_root=tmp_path,
        run_id="must-not-run",
    )

    assert FROZEN_MODEL == "glm-5-2-260617"
    with pytest.raises(ValueError, match="frozen model"):
        asyncio.run(run_evaluation(args))
