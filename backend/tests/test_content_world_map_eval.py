from __future__ import annotations

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from scripts.run_content_world_map_eval import (
    CONTENT_WORLD_MAP_SYSTEM_PROMPT,
    build_map_messages,
    calculate_live_call_count,
    parse_content_world_map,
    run_map_case,
)
from scripts.run_marketing_brain_eval import default_cases


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def _case(case_id: str):
    return next(case for case in default_cases() if case.case_id == case_id)


def _valid_map() -> dict[str, object]:
    return {
        "known_facts": ["主体经营一个品类"],
        "semantic_parts": [
            {
                "term": "业务对象",
                "role": "category",
                "basis": "用户原话",
            }
        ],
        "candidate_worlds": [
            {
                "scale": "object_internal",
                "subject": "对象内部世界",
                "derivation": "从对象内部类型与状态展开",
                "expansion_axes": ["类型", "状态", "时间"],
                "business_relevance": "与业务对象保持直接关联",
                "limits": ["实际经营对象未核实"],
            }
        ],
        "material_unknowns": ["主体实际经营范围"],
        "insufficiency": None,
    }


def test_content_world_prompt_maps_semantics_without_solving_other_coordinates():
    prompt = CONTENT_WORLD_MAP_SYSTEM_PROMPT

    assert "可检查的语义内容地图" in prompt
    assert "不是最终起号方案" in prompt
    assert "object_internal" in prompt
    assert "use_action" in prompt
    assert "relation_need" in prompt
    assert "professional_task" in prompt
    assert "不要求主体独占" in prompt
    assert "不得设计人设、受众、平台、表现形式" in prompt
    assert "不得为了完整而强行生成固定数量" in prompt
    for leaked_case in ("黄金", "礼品", "水果", "花店", "宝妈", "脐橙"):
        assert leaked_case not in prompt


def test_map_messages_preserve_original_input_as_untrusted_data():
    question = "我经营一个产品，怎么起号？"
    messages = build_map_messages(question=question)

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == f"--- BEGIN USER INPUT ---\n{question}\n--- END USER INPUT ---"
    assert messages[1].additional_kwargs["original_user_content"] == question


def test_parse_content_world_map_accepts_variable_world_count_and_null_insufficiency():
    payload = _valid_map()
    parsed = parse_content_world_map(json.dumps(payload, ensure_ascii=False))

    assert parsed == payload

    payload["candidate_worlds"] = []
    payload["insufficiency"] = "只有身份线索，没有可分解的商业对象或价值主张"
    assert parse_content_world_map(json.dumps(payload, ensure_ascii=False)) == payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("known_facts", "不是列表"),
        ("semantic_parts", [{"term": "x", "role": "unknown"}]),
        ("candidate_worlds", [{"scale": "object_internal"}]),
        ("material_unknowns", [1]),
        ("insufficiency", []),
    ],
)
def test_parse_content_world_map_rejects_contract_drift(field, value):
    payload = _valid_map()
    payload[field] = value

    with pytest.raises(ValueError):
        parse_content_world_map(json.dumps(payload, ensure_ascii=False))


def test_live_call_count_is_only_models_times_cases_without_an_llm_judge():
    assert calculate_live_call_count(case_count=1, model_count=2) == 2
    assert calculate_live_call_count(case_count=4, model_count=2) == 8


def test_map_case_persists_visible_map_and_reasoning_hash_but_not_private_reasoning():
    payload = _valid_map()
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(payload, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_REASONING"},
            )
        ]
    )

    result = asyncio.run(run_map_case(model=model, model_name="test-model", case=_case("fruit-shop")))

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["content_world_map"] == payload
    assert result["provider_reasoning_present"] is True
    assert len(result["provider_reasoning_sha256"]) == 64
    assert "PRIVATE_REASONING" not in serialized
    assert len(model.calls) == 1
