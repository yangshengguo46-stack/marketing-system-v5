from __future__ import annotations

import asyncio
import json
from argparse import Namespace
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from scripts.run_relational_semantic_contrast_eval import (
    DECISION_SYSTEM_PROMPT,
    FROZEN_MODEL,
    RELATION_SYSTEM_PROMPT,
    build_decision_messages,
    build_relation_messages,
    calculate_primary_call_count,
    calculate_provider_call_budget,
    default_relational_pairs,
    parse_relation_analysis,
    parse_world_decision,
    review_pair_result,
    run_evaluation,
    run_relational_pair,
)


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def _pair(pair_id: str):
    return next(pair for pair in default_relational_pairs() if pair.pair_id == pair_id)


def _valid_relation() -> dict[str, object]:
    return {
        "relation": "same_root",
        "changed_factor": "经营容器与表达方式",
        "should_stay": "实际经营对象和对象世界",
        "left_candidate_roots": [
            {
                "id": "left-bread",
                "term": "面包",
                "root_kind": "object",
                "why_complete": "面包本身有品类、原料、时间、地域与文化差异",
                "return_path": "对象内容直接回到门店经营的面包",
                "overreach_risk": "扩大到饮食生活会失去面包根",
            }
        ],
        "right_candidate_roots": [
            {
                "id": "right-bread",
                "term": "面包",
                "root_kind": "object",
                "why_complete": "卖货动作不改变面包是完整对象",
                "return_path": "对象内容直接回到所售面包",
                "overreach_risk": "抬成早餐或烘焙过程会改变主语",
            }
        ],
        "over_abstraction_risk": "为了强调人与场景而把对象抬成日常饮食活动",
        "unknowns": [],
    }


def _decision(candidate_id: str) -> dict[str, object]:
    return {
        "source_object": "面包",
        "audience_world": "面包",
        "world_kind": "object",
        "selected_candidate_id": candidate_id,
        "candidate_relation": "selected_candidate",
        "reason": "两种表达的完整经营对象都是面包",
        "return_path": "内容中的面包对象直接返回原业务",
        "unknowns": [],
    }


def test_prompts_shift_attention_to_relation_before_root_selection():
    for required in ("只改变一个因素", "应保持", "应变化", "先比较", "不是市场因果证明"):
        assert required in RELATION_SYSTEM_PROMPT
    assert "允许纠正" in DECISION_SYSTEM_PROMPT

    prompts = RELATION_SYSTEM_PROMPT + DECISION_SYSTEM_PROMPT
    for theory_term in (
        "Qualia",
        "Formal",
        "Constitutive",
        "Agentive",
        "Telic",
        "JTBD",
        "concept bottleneck",
        "社会实践理论",
        "功能进展",
        "情绪进展",
        "社会进展",
    ):
        assert theory_term not in prompts
    for held_out_term in ("面包", "玻璃", "退休", "陶瓷", "月饼"):
        assert held_out_term not in prompts
    for prior_term in ("茶叶", "咖喱", "银饰", "黄金礼品", "水果店", "海鲜", "火锅底料", "腕表", "医美"):
        assert prior_term not in prompts


def test_four_new_pairs_use_eight_unique_cases_and_no_prior_case_ids():
    pairs = default_relational_pairs()
    assert [pair.pair_id for pair in pairs] == [
        "remove-business-container",
        "same-use-different-material",
        "same-material-different-use",
        "intermediate-style-substitution",
    ]
    case_ids = [case.case_id for pair in pairs for case in (pair.left, pair.right)]
    assert case_ids == [
        "bread-shop-container",
        "bread-direct-product",
        "glass-retirement-memento",
        "wood-retirement-memento",
        "ceramic-graduation-gift",
        "ceramic-tableware",
        "cantonese-mooncake-filling",
        "suzhou-mooncake-filling",
    ]
    assert len(case_ids) == len(set(case_ids)) == 8
    prior_ids = {
        "tea-shop-container",
        "tea-direct-product",
        "silver-business-gift",
        "wood-business-gift",
        "silver-jewelry",
        "japanese-curry-block",
        "thai-curry-sauce",
        "gold-gift",
        "fruit-shop",
        "seafood-source",
        "chongqing-hotpot-base",
        "watch-account",
        "medical-aesthetics-account",
    }
    assert prior_ids.isdisjoint(case_ids)


def test_hidden_relation_and_acceptance_never_enter_model_messages():
    pair = _pair("remove-business-container")
    relation = _valid_relation()
    messages = [
        *build_relation_messages(pair=pair),
        *build_decision_messages(pair=pair, target_side="left", relation=relation),
    ]
    payload = "\n".join(str(message.content) for message in messages)
    for hidden_key in (
        "expected_relation",
        "acceptance",
        "source_signal_groups",
        "world_signal_groups",
        "forbidden_world_signals",
        "expected_world_kind",
        "shared_world_signal_groups",
    ):
        assert hidden_key not in payload
    assert "烘焙食品对象根" not in payload


def test_relation_parser_allows_uncertainty_and_empty_candidates():
    payload = {
        "relation": "uncertain",
        "changed_factor": None,
        "should_stay": None,
        "left_candidate_roots": [],
        "right_candidate_roots": [],
        "over_abstraction_risk": None,
        "unknowns": [],
    }
    assert parse_relation_analysis(json.dumps(payload, ensure_ascii=False)) == payload


def test_relation_parser_rejects_scores_duplicate_ids_and_extra_fields():
    candidate = dict(_valid_relation()["left_candidate_roots"][0])
    candidate["score"] = 0.9
    with pytest.raises(ValueError, match="left candidate root"):
        parse_relation_analysis(json.dumps({**_valid_relation(), "left_candidate_roots": [candidate]}, ensure_ascii=False))

    duplicate = dict(_valid_relation()["right_candidate_roots"][0])
    duplicate["id"] = "left-bread"
    with pytest.raises(ValueError, match="unique across both sides"):
        parse_relation_analysis(json.dumps({**_valid_relation(), "right_candidate_roots": [duplicate]}, ensure_ascii=False))


def test_decision_can_select_only_its_side_or_correct_the_relation_analysis():
    relation = parse_relation_analysis(json.dumps(_valid_relation(), ensure_ascii=False))
    selected = parse_world_decision(json.dumps(_decision("left-bread"), ensure_ascii=False), relation=relation, target_side="left")
    assert selected["selected_candidate_id"] == "left-bread"

    corrected_payload = {
        **_decision("left-bread"),
        "selected_candidate_id": None,
        "candidate_relation": "corrected_candidate",
    }
    corrected = parse_world_decision(json.dumps(corrected_payload, ensure_ascii=False), relation=relation, target_side="left")
    assert corrected["candidate_relation"] == "corrected_candidate"

    with pytest.raises(ValueError, match="target-side candidate"):
        parse_world_decision(json.dumps(_decision("right-bread"), ensure_ascii=False), relation=relation, target_side="left")


def test_hidden_review_separates_relation_candidate_and_final_failures():
    pair = _pair("remove-business-container")
    relation = {**_valid_relation(), "relation": "different_root"}
    left_decision = _decision("left-bread")
    right_decision = {
        **_decision("right-bread"),
        "audience_world": "早餐消费",
        "world_kind": "activity_or_practice",
    }

    review = review_pair_result(
        pair=pair,
        relation=relation,
        left_decision=left_decision,
        right_decision=right_decision,
    )

    assert review["relation_judgment"] == "failed"
    assert review["left_candidate_recall"] == "passed"
    assert review["right_candidate_recall"] == "passed"
    assert review["left_final_convergence"] == "passed"
    assert review["right_final_convergence"] == "failed"
    assert review["final_contrast"] == "failed"
    assert review["status"] == "failed_business"


def test_pair_run_shares_one_relation_with_both_decisions_and_hashes_reasoning():
    pair = _pair("remove-business-container")
    relation = _valid_relation()
    left_decision = _decision("left-bread")
    right_decision = _decision("right-bread")
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(relation, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_RELATION_REASONING"},
            ),
            AIMessage(
                content=json.dumps(left_decision, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_LEFT_REASONING"},
            ),
            AIMessage(
                content=json.dumps(right_decision, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_RIGHT_REASONING"},
            ),
        ]
    )

    result = asyncio.run(run_relational_pair(model=model, model_name="test-model", pair=pair))

    assert result["relation_analysis"] == relation
    assert result["left_decision"] == left_decision
    assert result["right_decision"] == right_decision
    assert result["automatic_review"]["status"] == "passed"
    assert result["provider_calls"] == 3
    assert json.loads(model.calls[1][1].content)["relation_analysis"] == relation
    assert json.loads(model.calls[2][1].content)["relation_analysis"] == relation
    serialized = json.dumps(result, ensure_ascii=False)
    for private_text in ("PRIVATE_RELATION_REASONING", "PRIVATE_LEFT_REASONING", "PRIVATE_RIGHT_REASONING"):
        assert private_text not in serialized
    assert len(result["provider_reasoning_sha256"]) == 64


def test_schema_repairs_receive_contract_errors_but_not_hidden_business_labels():
    pair = _pair("remove-business-container")
    relation = _valid_relation()
    left_decision = _decision("left-bread")
    right_decision = _decision("right-bread")
    model = FakeModel(
        [
            AIMessage(content=json.dumps({**relation, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(relation, ensure_ascii=False)),
            AIMessage(content=json.dumps({**left_decision, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(left_decision, ensure_ascii=False)),
            AIMessage(content=json.dumps(right_decision, ensure_ascii=False)),
        ]
    )

    result = asyncio.run(
        run_relational_pair(
            model=model,
            model_name="test-model",
            pair=pair,
            max_relation_repair_calls=1,
            max_decision_repair_calls=1,
        )
    )

    assert result["stage_repairs"] == {"relation": 1, "left_decision": 1, "right_decision": 0}
    for repair_call in (model.calls[1], model.calls[3]):
        repair_prompt = repair_call[-1].content
        assert "只修复 JSON 契约" in repair_prompt
        assert "不要重新做业务判断" in repair_prompt
        assert "面包" not in repair_prompt
        assert "same_root" not in repair_prompt


def test_call_budget_is_four_relation_calls_plus_eight_decisions_and_two_shared_repairs():
    assert calculate_primary_call_count(pair_count=4, model_count=1) == 12
    assert (
        calculate_provider_call_budget(
            primary_calls=12,
            max_relation_repair_calls=1,
            max_decision_repair_calls=1,
        )
        == 14
    )


def test_live_runner_rejects_any_model_outside_the_preregistered_single_model(tmp_path: Path):
    args = Namespace(
        execute=True,
        models=["unfrozen-model"],
        pair_ids=[],
        max_calls=12,
        max_relation_repair_calls=1,
        max_decision_repair_calls=1,
        seed=80,
        output_root=tmp_path,
        run_id="must-not-run",
    )
    assert FROZEN_MODEL == "glm-5-2-260617"
    with pytest.raises(ValueError, match="frozen model"):
        asyncio.run(run_evaluation(args))
