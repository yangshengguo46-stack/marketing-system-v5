from __future__ import annotations

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from scripts.run_two_step_content_map_eval import (
    EXPANSION_SYSTEM_PROMPT,
    SKELETON_SYSTEM_PROMPT,
    build_expansion_messages,
    build_skeleton_messages,
    calculate_primary_call_count,
    calculate_provider_call_budget,
    compose_layered_map,
    default_two_step_cases,
    parse_expansion,
    parse_skeleton,
    run_two_step_case,
    validate_two_step_map_against_case,
)


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def _case(case_id: str):
    return next(case for case in default_two_step_cases() if case.case_id == case_id)


def _valid_skeleton() -> dict[str, object]:
    return {
        "source_object": {
            "term": "水果",
            "basis": "门店是经营容器，用户明确经营的对象是水果",
            "evidence_refs": ["business-1"],
        },
        "audience_world": {
            "term": "水果",
            "relation_to_source": "same_object_world",
            "selection_basis": "水果本身是可长期展开的完整对象世界",
            "source_relation": "业务对象与观众内容世界直接重合",
            "evidence_refs": ["business-1"],
            "support": "inferred",
        },
        "content_engines": [
            {
                "id": "engine-object",
                "subject": "水果种类与差异",
                "content_function": "object_exploration",
                "basis": "不同子类可持续产生比较和知识",
                "evidence_refs": ["business-1"],
                "support": "inferred",
            }
        ],
        "attention_entries": [
            {
                "id": "attention-question",
                "carrier": "普通人熟悉的水果问题",
                "mechanism": "从已有生活经验进入水果世界",
                "basis": "这是类别级入口，具体问题仍需研究",
                "evidence_refs": ["business-1"],
                "support": "research_hypothesis",
            }
        ],
        "unknowns": ["具体品类与经营者经验未知"],
        "insufficiency": None,
    }


def _valid_expansion() -> dict[str, object]:
    return {
        "expansion_nodes": [
            {
                "id": "node-types",
                "parent_type": "audience_world",
                "parent_id": "audience_world",
                "axis": "types_and_subworlds",
                "direction": "不同水果种类及其子世界",
                "connection": "种类差异直接改变水果对象的特征与使用情境",
                "evidence_refs": ["business-1"],
                "support": "research_hypothesis",
                "research_needed": True,
            },
            {
                "id": "node-history",
                "parent_type": "content_engine",
                "parent_id": "engine-object",
                "axis": "time_and_history",
                "direction": "水果品种与食用方式的历史变化",
                "connection": "时间会改变品种传播和人们理解水果的方式",
                "evidence_refs": ["business-1"],
                "support": "research_hypothesis",
                "research_needed": True,
            },
        ],
        "unknowns": ["具体历史事实需另行核验"],
        "insufficiency": None,
    }


def test_prompts_separate_skeleton_selection_from_bounded_expansion():
    for required in (
        "原始业务对象",
        "观众内容世界",
        "内容发动机",
        "注意力入口",
        "去经营容器反事实",
        "去修饰条件反事实",
        "去发动机反事实",
        "最小完整根",
    ):
        assert required in SKELETON_SYSTEM_PROMPT
    assert "expansion_nodes" not in SKELETON_SYSTEM_PROMPT
    assert "time_and_history" not in SKELETON_SYSTEM_PROMPT

    for required in (
        "冻结骨架",
        "不得重新判断",
        "不得改写",
        "八个轴",
        "parent_id",
        "research_needed",
    ):
        assert required in EXPANSION_SYSTEM_PROMPT
    assert '"source_object"' not in EXPANSION_SYSTEM_PROMPT
    assert '"audience_world"' not in EXPANSION_SYSTEM_PROMPT
    assert '"content_engines"' not in EXPANSION_SYSTEM_PROMPT
    assert '"attention_entries"' not in EXPANSION_SYSTEM_PROMPT

    combined = SKELETON_SYSTEM_PROMPT + EXPANSION_SYSTEM_PROMPT
    for term in ("卖货", "销售", "广告", "变现", "成交", "转化", "带货"):
        assert term not in combined
    for leaked_gold in ("黄金礼品", "水果店", "海鲜", "火锅底料", "腕表", "医美"):
        assert leaked_gold not in combined


def test_six_cases_are_reused_but_review_labels_are_not_model_visible():
    cases = default_two_step_cases()
    assert [case.case_id for case in cases] == [
        "gold-gift",
        "fruit-shop",
        "seafood-source",
        "chongqing-hotpot-base",
        "watch-account",
        "medical-aesthetics-account",
    ]

    case = _case("fruit-shop")
    skeleton_messages = build_skeleton_messages(case=case)
    assert isinstance(skeleton_messages[0], SystemMessage)
    assert isinstance(skeleton_messages[1], HumanMessage)
    payload = json.loads(skeleton_messages[1].content)
    for hidden in ("acceptance", "review_expectations", "source_terms", "world_terms", "required_axes"):
        assert hidden not in payload


def test_skeleton_parser_is_strict_and_has_no_expansion_surface():
    skeleton = _valid_skeleton()
    assert parse_skeleton(json.dumps(skeleton, ensure_ascii=False)) == skeleton

    skeleton["expansion_nodes"] = []
    with pytest.raises(ValueError, match="exactly"):
        parse_skeleton(json.dumps(skeleton, ensure_ascii=False))


def test_expansion_parser_cannot_rewrite_the_frozen_skeleton():
    skeleton = _valid_skeleton()
    expansion = _valid_expansion()
    assert parse_expansion(json.dumps(expansion, ensure_ascii=False), skeleton=skeleton) == expansion

    expansion["audience_world"] = {"term": "生活方式"}
    with pytest.raises(ValueError, match="exactly"):
        parse_expansion(json.dumps(expansion, ensure_ascii=False), skeleton=skeleton)


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value["expansion_nodes"][0].update({"parent_type": "content_engine", "parent_id": "missing-engine"}),
            "missing",
        ),
        (lambda value: value["expansion_nodes"][0].update({"research_needed": False}), "research_needed"),
        (lambda value: value["expansion_nodes"][0].update({"axis": "positioning"}), "axis"),
    ],
)
def test_expansion_nodes_must_be_rooted_and_unverified(mutate, error):
    skeleton = _valid_skeleton()
    expansion = _valid_expansion()
    mutate(expansion)

    with pytest.raises(ValueError, match=error):
        parse_expansion(json.dumps(expansion, ensure_ascii=False), skeleton=skeleton)


def test_expansion_messages_receive_exact_frozen_skeleton_without_gold():
    case = _case("fruit-shop")
    skeleton = _valid_skeleton()
    messages = build_expansion_messages(case=case, skeleton=skeleton)

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    payload = json.loads(messages[1].content)
    assert payload["frozen_skeleton"] == skeleton
    assert payload["evidence"]
    for hidden in ("acceptance", "review_expectations", "world_terms", "required_axes"):
        assert hidden not in payload


def test_composition_preserves_the_skeleton_byte_for_byte():
    skeleton = _valid_skeleton()
    expansion = _valid_expansion()
    frozen_fields = ("source_object", "audience_world", "content_engines", "attention_entries")
    before = json.dumps({key: skeleton[key] for key in frozen_fields}, ensure_ascii=False, sort_keys=True)

    combined = compose_layered_map(skeleton=skeleton, expansion=expansion)

    after = json.dumps({key: combined[key] for key in frozen_fields}, ensure_ascii=False, sort_keys=True)
    assert after == before
    assert combined["expansion_nodes"] == expansion["expansion_nodes"]
    assert combined["unknowns"] == [*skeleton["unknowns"], *expansion["unknowns"]]


def test_two_step_run_freezes_stage_one_before_stage_two_and_hashes_reasoning():
    case = _case("fruit-shop")
    skeleton = _valid_skeleton()
    expansion = _valid_expansion()
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(skeleton, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_SKELETON_REASONING"},
            ),
            AIMessage(
                content=json.dumps(expansion, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_EXPANSION_REASONING"},
            ),
        ]
    )

    result = asyncio.run(run_two_step_case(model=model, model_name="test-model", case=case))

    assert result["two_step_content_map"] == compose_layered_map(skeleton=skeleton, expansion=expansion)
    assert result["provider_calls"] == 2
    assert result["stage_calls"] == {"skeleton": 1, "expansion": 1}
    second_payload = json.loads(model.calls[1][1].content)
    assert second_payload["frozen_skeleton"] == skeleton
    serialized = json.dumps(result, ensure_ascii=False)
    assert "PRIVATE_SKELETON_REASONING" not in serialized
    assert "PRIVATE_EXPANSION_REASONING" not in serialized
    assert len(result["provider_reasoning_sha256"]) == 64


def test_each_stage_has_only_schema_repair_not_business_reconsideration():
    case = _case("fruit-shop")
    skeleton = _valid_skeleton()
    expansion = _valid_expansion()
    model = FakeModel(
        [
            AIMessage(content=json.dumps({**skeleton, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(skeleton, ensure_ascii=False)),
            AIMessage(content=json.dumps({**expansion, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(expansion, ensure_ascii=False)),
        ]
    )

    result = asyncio.run(
        run_two_step_case(
            model=model,
            model_name="test-model",
            case=case,
            max_skeleton_repair_calls=1,
            max_expansion_repair_calls=1,
        )
    )

    assert result["stage_repairs"] == {"skeleton": 1, "expansion": 1}
    assert len(model.calls) == 4
    for repair_call in (model.calls[1], model.calls[3]):
        assert "只修复 JSON 契约" in repair_call[-1].content
        assert "不要重新做内容判断" in repair_call[-1].content


def test_skeleton_contract_failure_stops_before_expansion_and_is_redacted():
    case = _case("fruit-shop")
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps({"wrong": "PRIVATE_VISIBLE"}, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_REASONING"},
            )
        ]
    )

    result = asyncio.run(run_two_step_case(model=model, model_name="test-model", case=case))

    assert result["two_step_content_map"] is None
    assert result["automatic_review"]["status"] == "failed_skeleton_contract"
    assert result["provider_calls"] == 1
    assert result["stage_calls"] == {"skeleton": 1, "expansion": 0}
    assert len(model.calls) == 1
    serialized = json.dumps(result, ensure_ascii=False)
    assert "PRIVATE_VISIBLE" not in serialized
    assert "PRIVATE_REASONING" not in serialized


def test_hidden_case_review_runs_only_after_both_stages():
    payload = compose_layered_map(skeleton=_valid_skeleton(), expansion=_valid_expansion())
    validate_two_step_map_against_case(payload, case=None)

    with pytest.raises(ValueError, match="missing reviewed expansion axes"):
        validate_two_step_map_against_case(payload, case=_case("fruit-shop"))


def test_two_step_call_budget_is_explicit_and_has_no_judge():
    assert calculate_primary_call_count(case_count=6, model_count=1) == 12
    assert (
        calculate_provider_call_budget(
            primary_calls=12,
            max_skeleton_repair_calls=1,
            max_expansion_repair_calls=1,
        )
        == 14
    )
