from __future__ import annotations

import asyncio
import json
from argparse import Namespace
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from scripts.run_actor_role_semantic_contrast_eval import (
    DECISION_SYSTEM_PROMPT,
    FROZEN_MODEL,
    ROLE_RELATION_SYSTEM_PROMPT,
    build_decision_messages,
    build_role_relation_messages,
    calculate_primary_call_count,
    calculate_provider_call_budget,
    default_actor_role_pairs,
    parse_role_relation_analysis,
    parse_world_decision,
    review_pair_result,
    run_actor_role_pair,
    run_evaluation,
)


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def _pair(pair_id: str):
    return next(pair for pair in default_actor_role_pairs() if pair.pair_id == pair_id)


def _option(
    option_id: str,
    term: str,
    role: str,
    disposition: str,
    root_kind: str,
) -> dict[str, object]:
    return {
        "id": option_id,
        "term": term,
        "actor_role": role,
        "disposition": disposition,
        "root_kind": root_kind,
        "basis": f"{term}在当前表达中的作用与边界",
        "return_path": f"{term}与原业务的直接连接",
        "overreach_risk": f"把{term}放在错误角色会导致根漂移",
    }


def _valid_analysis() -> dict[str, object]:
    return {
        "relation": "same_root",
        "changed_factor": "经营容器与销售表达",
        "should_stay": "儿童图书这一完整对象",
        "left_options": [
            _option("left-books", "儿童图书", "complete_object", "root_candidate", "object"),
            _option("left-reading", "阅读", "buyer_ordinary_use", "support_only", "activity_or_practice"),
        ],
        "right_options": [
            _option("right-books", "儿童图书", "complete_object", "root_candidate", "object"),
            _option("right-reading", "阅读", "buyer_ordinary_use", "support_only", "activity_or_practice"),
        ],
        "unknowns": [],
    }


def _decision(candidate_id: str) -> dict[str, object]:
    return {
        "source_object": "儿童图书",
        "audience_world": "儿童图书",
        "world_kind": "object",
        "selected_option_id": candidate_id,
        "option_relation": "selected_option",
        "reason": "阅读是买方普通使用，经营容器不改变完整图书对象",
        "return_path": "内容中的儿童图书直接回到原业务",
        "unknowns": [],
    }


def test_prompts_add_only_actor_role_distinction_to_relation_first_reasoning():
    for required in (
        "完整对象",
        "卖方操作或证明",
        "买方普通使用",
        "买方反复社会实践或长期结果",
        "先比较",
        "不是关键词硬门",
    ):
        assert required in ROLE_RELATION_SYSTEM_PROMPT
    assert "允许纠正" in DECISION_SYSTEM_PROMPT

    prompts = ROLE_RELATION_SYSTEM_PROMPT + DECISION_SYSTEM_PROMPT
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
    for held_out_term in ("童书", "儿童图书", "皮鞋", "婚礼请柬", "记事本", "饺子"):
        assert held_out_term not in prompts
    for prior_term in ("面包", "月饼", "退休纪念", "陶瓷", "茶叶", "咖喱", "黄金礼品"):
        assert prior_term not in prompts


def test_four_new_pairs_use_eight_unique_cases_without_prior_ids():
    pairs = default_actor_role_pairs()
    assert [pair.pair_id for pair in pairs] == [
        "remove-business-container",
        "seller-operation-substitution",
        "same-material-different-use",
        "intermediate-style-substitution",
    ]
    case_ids = [case.case_id for pair in pairs for case in (pair.left, pair.right)]
    assert case_ids == [
        "children-bookshop-container",
        "children-books-direct",
        "custom-leather-shoes",
        "ready-made-leather-shoes",
        "paper-wedding-invitation",
        "paper-notebook",
        "sichuan-dumpling-filling",
        "northern-dumpling-filling",
    ]
    assert len(case_ids) == len(set(case_ids)) == 8
    assert not any("bread" in case_id or "mooncake" in case_id or "tea" in case_id for case_id in case_ids)


def test_hidden_acceptance_and_role_expectations_never_enter_messages():
    pair = _pair("remove-business-container")
    analysis = _valid_analysis()
    messages = [
        *build_role_relation_messages(pair=pair),
        *build_decision_messages(pair=pair, target_side="left", analysis=analysis),
    ]
    payload = "\n".join(str(message.content) for message in messages)
    for hidden_key in (
        "expected_relation",
        "acceptance",
        "source_signal_groups",
        "world_signal_groups",
        "expected_world_kind",
        "role_expectations",
        "shared_world_signal_groups",
    ):
        assert hidden_key not in payload
    assert "童书对象根金标" not in payload


def test_role_relation_parser_allows_uncertainty_and_empty_options():
    payload = {
        "relation": "uncertain",
        "changed_factor": None,
        "should_stay": None,
        "left_options": [],
        "right_options": [],
        "unknowns": [],
    }
    assert parse_role_relation_analysis(json.dumps(payload, ensure_ascii=False)) == payload


def test_role_relation_parser_rejects_scores_duplicate_ids_and_unknown_roles():
    option = dict(_valid_analysis()["left_options"][0])
    option["score"] = 90
    with pytest.raises(ValueError, match="left option"):
        parse_role_relation_analysis(json.dumps({**_valid_analysis(), "left_options": [option]}, ensure_ascii=False))

    duplicate = dict(_valid_analysis()["right_options"][0])
    duplicate["id"] = "left-books"
    with pytest.raises(ValueError, match="unique across both sides"):
        parse_role_relation_analysis(json.dumps({**_valid_analysis(), "right_options": [duplicate]}, ensure_ascii=False))

    unknown = dict(_valid_analysis()["left_options"][0])
    unknown["actor_role"] = "marketing_magic"
    with pytest.raises(ValueError, match="actor_role"):
        parse_role_relation_analysis(json.dumps({**_valid_analysis(), "left_options": [unknown]}, ensure_ascii=False))


def test_decision_selects_only_target_root_options_or_explicitly_corrects():
    analysis = parse_role_relation_analysis(json.dumps(_valid_analysis(), ensure_ascii=False))
    selected = parse_world_decision(json.dumps(_decision("left-books"), ensure_ascii=False), analysis=analysis, target_side="left")
    assert selected["selected_option_id"] == "left-books"

    with pytest.raises(ValueError, match="root_candidate"):
        parse_world_decision(json.dumps(_decision("left-reading"), ensure_ascii=False), analysis=analysis, target_side="left")

    corrected_payload = {
        **_decision("left-books"),
        "selected_option_id": None,
        "option_relation": "corrected_option",
    }
    corrected = parse_world_decision(json.dumps(corrected_payload, ensure_ascii=False), analysis=analysis, target_side="left")
    assert corrected["option_relation"] == "corrected_option"


def test_hidden_review_scores_actor_roles_separately_from_roots():
    pair = _pair("remove-business-container")
    analysis = _valid_analysis()
    wrong_role = dict(analysis["left_options"][1])
    wrong_role["actor_role"] = "buyer_social_practice_or_result"
    wrong_role["disposition"] = "root_candidate"
    analysis = {**analysis, "left_options": [analysis["left_options"][0], wrong_role]}

    review = review_pair_result(
        pair=pair,
        analysis=analysis,
        left_decision=_decision("left-books"),
        right_decision=_decision("right-books"),
    )

    assert review["relation_judgment"] == "passed"
    assert review["left_candidate_recall"] == "passed"
    assert review["right_candidate_recall"] == "passed"
    assert review["left_final_convergence"] == "passed"
    assert review["right_final_convergence"] == "passed"
    assert review["final_contrast"] == "passed"
    assert review["role_expectations_passed"] == review["role_expectations_total"] - 1
    assert review["status"] == "failed_business"


def test_pair_run_shares_role_analysis_with_both_decisions_and_hashes_reasoning():
    pair = _pair("remove-business-container")
    analysis = _valid_analysis()
    left_decision = _decision("left-books")
    right_decision = _decision("right-books")
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(analysis, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_ROLE_REASONING"},
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

    result = asyncio.run(run_actor_role_pair(model=model, model_name="test-model", pair=pair))

    assert result["role_relation_analysis"] == analysis
    assert result["left_decision"] == left_decision
    assert result["right_decision"] == right_decision
    assert result["automatic_review"]["status"] == "passed"
    assert result["provider_calls"] == 3
    assert json.loads(model.calls[1][1].content)["role_relation_analysis"] == analysis
    assert json.loads(model.calls[2][1].content)["role_relation_analysis"] == analysis
    serialized = json.dumps(result, ensure_ascii=False)
    for private_text in ("PRIVATE_ROLE_REASONING", "PRIVATE_LEFT_REASONING", "PRIVATE_RIGHT_REASONING"):
        assert private_text not in serialized
    assert len(result["provider_reasoning_sha256"]) == 64


def test_schema_repairs_do_not_receive_hidden_roles_or_labels():
    pair = _pair("remove-business-container")
    analysis = _valid_analysis()
    left_decision = _decision("left-books")
    right_decision = _decision("right-books")
    model = FakeModel(
        [
            AIMessage(content=json.dumps({**analysis, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(analysis, ensure_ascii=False)),
            AIMessage(content=json.dumps({**left_decision, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(left_decision, ensure_ascii=False)),
            AIMessage(content=json.dumps(right_decision, ensure_ascii=False)),
        ]
    )

    result = asyncio.run(
        run_actor_role_pair(
            model=model,
            model_name="test-model",
            pair=pair,
            max_role_repair_calls=1,
            max_decision_repair_calls=1,
        )
    )

    assert result["stage_repairs"] == {"role_relation": 1, "left_decision": 1, "right_decision": 0}
    for repair_call in (model.calls[1], model.calls[3]):
        repair_prompt = repair_call[-1].content
        assert "只修复 JSON 契约" in repair_prompt
        assert "不要重新做业务判断" in repair_prompt
        assert "儿童图书" not in repair_prompt
        assert "buyer_ordinary_use" not in repair_prompt


def test_call_budget_stays_at_four_role_calls_plus_eight_decisions_and_two_repairs():
    assert calculate_primary_call_count(pair_count=4, model_count=1) == 12
    assert (
        calculate_provider_call_budget(
            primary_calls=12,
            max_role_repair_calls=1,
            max_decision_repair_calls=1,
        )
        == 14
    )


def test_live_runner_rejects_non_frozen_models(tmp_path: Path):
    args = Namespace(
        execute=True,
        models=["unfrozen-model"],
        pair_ids=[],
        max_calls=12,
        max_role_repair_calls=1,
        max_decision_repair_calls=1,
        seed=80,
        output_root=tmp_path,
        run_id="must-not-run",
    )
    assert FROZEN_MODEL == "glm-5-2-260617"
    with pytest.raises(ValueError, match="frozen model"):
        asyncio.run(run_evaluation(args))
