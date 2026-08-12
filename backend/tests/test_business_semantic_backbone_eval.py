from __future__ import annotations

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from scripts.run_business_semantic_backbone_eval import (
    BUSINESS_SEMANTIC_BACKBONE_SYSTEM_PROMPT,
    build_backbone_messages,
    parse_business_semantic_backbone,
    run_backbone_case,
)
from scripts.run_marketing_brain_eval import default_cases


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


class HangingModel:
    async def ainvoke(self, messages):
        await asyncio.Event().wait()


def _case(case_id: str):
    return next(case for case in default_cases() if case.case_id == case_id)


def _valid_backbone() -> dict[str, object]:
    return {
        "known_facts": ["主体从事一种组合品类的生产"],
        "commercial_expression": "属性品类生产",
        "plain_paraphrases": ["主体生产一种带有属性的品类"],
        "offer_object": {
            "term": "属性品类",
            "semantic_head": "品类",
            "support": "lexical_semantics",
            "basis": "品类决定组合表达所指的商业对象，属性只修饰品类",
        },
        "operating_containers": [
            {
                "term": "经营载体",
                "target": "属性品类",
                "support": "explicit",
                "basis": "用户明确说明通过该载体经营品类",
            }
        ],
        "qualifiers": [
            {
                "term": "属性",
                "relation": "material_or_attribute",
                "target": "品类",
                "support": "lexical_semantics",
                "basis": "属性说明品类的材料或特征",
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
                "basis": "这是品类词义推断，不是主体客户事实",
            }
        ],
        "buyer_progresses": [
            {
                "progress": "借助该品类完成对应任务",
                "support": "lexical_semantics",
                "basis": "这是通用品类语义，不代表已知实际买方",
            }
        ],
        "ambiguities": ["实际交易的是成品还是生产服务未知"],
        "insufficiency": None,
    }


def test_backbone_prompt_only_explicitates_business_semantics():
    prompt = BUSINESS_SEMANTIC_BACKBONE_SYSTEM_PROMPT

    assert "商业语义骨架" in prompt
    assert "不是内容世界选择器" in prompt
    assert "经营载体" in prompt
    assert "商业对象" in prompt
    assert "语义主词" in prompt
    assert "卖方动作" in prompt
    assert "品类构成功能" in prompt
    assert "买方期望进展" in prompt
    assert "不能只按句尾词或语法主词" in prompt
    assert "lexical_semantics" in prompt
    assert "不得输出人设、受众、平台、表现形式" in prompt
    for leaked_case in ("黄金", "礼品", "水果", "花店", "宝妈", "脐橙"):
        assert leaked_case not in prompt


def test_backbone_messages_preserve_original_input_as_untrusted_data():
    question = "我经营一种产品，怎么起号？"
    messages = build_backbone_messages(question=question)

    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == BUSINESS_SEMANTIC_BACKBONE_SYSTEM_PROMPT
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == f"--- BEGIN USER INPUT ---\n{question}\n--- END USER INPUT ---"
    assert messages[1].additional_kwargs["original_user_content"] == question


def test_parse_backbone_accepts_explicit_and_lexical_support_without_mixing_them():
    payload = _valid_backbone()
    assert parse_business_semantic_backbone(json.dumps(payload, ensure_ascii=False)) == payload

    payload["offer_object"] = None
    payload["operating_containers"] = []
    payload["qualifiers"] = []
    payload["seller_activities"] = []
    payload["constitutive_functions"] = []
    payload["buyer_progresses"] = []
    payload["insufficiency"] = "只有身份，没有商业对象"
    assert parse_business_semantic_backbone(json.dumps(payload, ensure_ascii=False)) == payload


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda p: p["qualifiers"][0].update(support="invented"), "support"),
        (lambda p: p["seller_activities"][0].update(relation="operates"), "fields"),
        (lambda p: p["offer_object"].update(extra="drift"), "fields"),
        (lambda p: p.update(insufficiency=[]), "insufficiency"),
    ],
)
def test_parse_backbone_rejects_schema_and_provenance_drift(mutate, error):
    payload = _valid_backbone()
    mutate(payload)

    with pytest.raises(ValueError, match=error):
        parse_business_semantic_backbone(json.dumps(payload, ensure_ascii=False))


def test_parse_backbone_requires_insufficiency_when_no_offer_object_exists():
    payload = _valid_backbone()
    payload["offer_object"] = None

    with pytest.raises(ValueError, match="requires insufficiency"):
        parse_business_semantic_backbone(json.dumps(payload, ensure_ascii=False))


def test_run_backbone_case_persists_visible_structure_not_private_reasoning():
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(_valid_backbone(), ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_BACKBONE_REASONING"},
            )
        ]
    )

    result = asyncio.run(
        run_backbone_case(
            model=model,
            model_name="test-model",
            case=_case("gold-gift"),
        )
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["business_semantic_backbone"] == _valid_backbone()
    assert result["provider_reasoning_present"] is True
    assert len(result["provider_reasoning_sha256"]) == 64
    assert "PRIVATE_BACKBONE_REASONING" not in serialized
    assert len(model.calls) == 1


def test_run_backbone_case_times_out_a_stalled_provider_call():
    with pytest.raises(TimeoutError):
        asyncio.run(
            run_backbone_case(
                model=HangingModel(),
                model_name="stalled-model",
                case=_case("gold-gift"),
                timeout_seconds=0.01,
            )
        )
