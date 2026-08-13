from __future__ import annotations

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from scripts.run_semantic_concept_bottleneck_eval import (
    CONCEPT_SYSTEM_PROMPT,
    DECISION_SYSTEM_PROMPT,
    build_concept_messages,
    build_decision_messages,
    calculate_primary_call_count,
    calculate_provider_call_budget,
    default_concept_bottleneck_cases,
    parse_concept_bottleneck,
    parse_world_decision,
    run_concept_bottleneck_case,
    validate_bottleneck_result_against_case,
)


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def _case(case_id: str):
    return next(case for case in default_concept_bottleneck_cases() if case.case_id == case_id)


def _concept_item(term: str) -> dict[str, object]:
    return {
        "term": term,
        "basis": f"{term}来自用户明确表达或有界语义推断",
        "evidence_refs": ["business-1"],
        "support": "inferred",
    }


def _valid_concepts() -> dict[str, object]:
    return {
        "semantic_roles": {
            "formal_object": _concept_item("水果"),
            "constitutive_elements": [],
            "agentive_operations": [],
            "telic_uses": [_concept_item("食用")],
            "business_containers": [_concept_item("门店")],
        },
        "human_job_and_frame": {
            "functional_progress": [],
            "emotional_progress": [],
            "social_progress": [],
            "actors": [],
            "occasions": [],
            "norms_or_tensions": [],
        },
        "practice_candidates": [],
        "candidate_worlds": [
            {
                "id": "world-object",
                "term": "水果",
                "world_type": "object_world",
                "source_relation": "水果本身就是可持续展开的完整对象",
                "capacity_basis": "有种类、历史、地域和文化差异",
                "direct_return_path": "内容中的水果直接返回门店经营的水果",
                "risk": "可能退化成零散品类百科",
                "evidence_refs": ["business-1"],
                "support": "inferred",
            },
            {
                "id": "world-use",
                "term": "食用水果",
                "world_type": "activity_or_job_world",
                "source_relation": "水果可被食用",
                "capacity_basis": "存在选择和食用情境",
                "direct_return_path": "食用可返回水果",
                "risk": "日常动作过泛，可能不如水果对象完整",
                "evidence_refs": ["business-1"],
                "support": "research_hypothesis",
            },
        ],
        "contrastive_probes": [
            {
                "operation": "remove_container",
                "target": "门店",
                "question": "去掉经营容器后，什么对象仍然成立？",
                "expected_observation": "水果仍成立",
                "basis": "门店不改变经营对象",
            }
        ],
        "unknowns": ["具体经营品类未知"],
    }


def _valid_decision() -> dict[str, object]:
    return {
        "source_object": {
            "term": "水果",
            "basis": "去掉门店后保留实际经营对象",
            "evidence_refs": ["business-1"],
        },
        "audience_world": {
            "term": "水果",
            "world_type": "object_world",
            "selected_candidate_id": "world-object",
            "concept_relation": "selected_candidate",
            "selection_basis": "水果对象比泛化食用动作更完整",
            "source_relation": "内容对象与业务对象直接重合",
            "evidence_refs": ["business-1"],
            "support": "inferred",
        },
        "rejected_candidate_ids": ["world-use"],
        "unknowns": ["具体经营品类未知"],
    }


def test_prompts_externalize_concepts_without_turning_them_into_a_hard_workflow():
    for required in (
        "Formal",
        "Constitutive",
        "Agentive",
        "Telic",
        "功能进展",
        "情绪进展",
        "社会进展",
        "材料",
        "能力",
        "意义与规范",
        "对象世界",
        "活动或任务世界",
        "社会实践世界",
        "欲望或结果世界",
        "允许为空",
        "不能为完整而补造",
        "语义消融",
    ):
        assert required in CONCEPT_SYSTEM_PROMPT

    for required in (
        "候选假设",
        "不是权威",
        "允许推翻",
        "原始业务对象",
        "观众内容世界",
        "只回答这两个判断",
    ):
        assert required in DECISION_SYSTEM_PROMPT

    combined = CONCEPT_SYSTEM_PROMPT + DECISION_SYSTEM_PROMPT
    for out_of_scope in (
        "内容发动机",
        "注意力入口",
        "表现形式",
        "变现路径",
        "发布计划",
        "实验周期",
        "评分",
    ):
        assert out_of_scope not in combined
    for leaked_case in ("黄金礼品", "水果店", "海鲜", "火锅底料", "腕表", "医美"):
        assert leaked_case not in combined


def test_six_frozen_cases_are_reused_but_hidden_labels_never_enter_messages():
    cases = default_concept_bottleneck_cases()
    assert [case.case_id for case in cases] == [
        "gold-gift",
        "fruit-shop",
        "seafood-source",
        "chongqing-hotpot-base",
        "watch-account",
        "medical-aesthetics-account",
    ]

    case = _case("gold-gift")
    messages = build_concept_messages(case=case)
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    payload = json.loads(messages[1].content)
    for hidden in ("acceptance", "review_expectations", "source_terms", "world_terms", "forbidden_world_terms"):
        assert hidden not in payload


def test_concept_parser_accepts_unknowns_and_empty_optional_concept_groups():
    payload = _valid_concepts()
    payload["semantic_roles"]["formal_object"] = None
    payload["semantic_roles"]["telic_uses"] = []
    payload["candidate_worlds"] = []

    assert parse_concept_bottleneck(json.dumps(payload, ensure_ascii=False)) == payload

    payload["score"] = 80
    with pytest.raises(ValueError, match="exactly"):
        parse_concept_bottleneck(json.dumps(payload, ensure_ascii=False))


def test_concept_parser_rejects_duplicate_ids_and_numeric_shortcuts():
    payload = _valid_concepts()
    payload["candidate_worlds"][1]["id"] = "world-object"
    with pytest.raises(ValueError, match="duplicate"):
        parse_concept_bottleneck(json.dumps(payload, ensure_ascii=False))

    payload = _valid_concepts()
    payload["candidate_worlds"][0]["capacity_score"] = 90
    with pytest.raises(ValueError, match="invalid fields"):
        parse_concept_bottleneck(json.dumps(payload, ensure_ascii=False))


def test_decision_may_select_or_explicitly_correct_the_concept_candidates():
    concepts = _valid_concepts()
    selected = _valid_decision()
    assert parse_world_decision(json.dumps(selected, ensure_ascii=False), concepts=concepts) == selected

    corrected = _valid_decision()
    corrected["audience_world"].update(
        {
            "term": "新判断",
            "selected_candidate_id": None,
            "concept_relation": "corrected_candidate",
        }
    )
    assert parse_world_decision(json.dumps(corrected, ensure_ascii=False), concepts=concepts) == corrected

    corrected["audience_world"]["selected_candidate_id"] = "missing"
    with pytest.raises(ValueError, match="selected_candidate_id"):
        parse_world_decision(json.dumps(corrected, ensure_ascii=False), concepts=concepts)

    no_candidates = _valid_concepts()
    no_candidates["candidate_worlds"] = []
    corrected["audience_world"]["selected_candidate_id"] = None
    corrected["rejected_candidate_ids"] = []
    assert parse_world_decision(json.dumps(corrected, ensure_ascii=False), concepts=no_candidates) == corrected


def test_decision_messages_expose_concepts_but_not_review_labels():
    case = _case("fruit-shop")
    concepts = _valid_concepts()
    messages = build_decision_messages(case=case, concepts=concepts)

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    payload = json.loads(messages[1].content)
    assert payload["concept_bottleneck"] == concepts
    for hidden in ("acceptance", "review_expectations", "world_terms", "forbidden_world_terms"):
        assert hidden not in payload


def test_hidden_review_distinguishes_candidate_recall_from_final_selection():
    case = _case("fruit-shop")
    concepts = _valid_concepts()
    decision = _valid_decision()

    review = validate_bottleneck_result_against_case(concepts=concepts, decision=decision, case=case)
    assert review == {
        "candidate_recall": "passed",
        "final_selection": "passed",
        "errors": [],
    }

    concepts["candidate_worlds"] = [concepts["candidate_worlds"][1]]
    decision["audience_world"].update(
        {
            "selected_candidate_id": None,
            "concept_relation": "corrected_candidate",
        }
    )
    review = validate_bottleneck_result_against_case(concepts=concepts, decision=decision, case=case)
    assert review["candidate_recall"] == "failed"
    assert review["final_selection"] == "passed"


def test_case_run_passes_the_inspectable_bottleneck_forward_and_hashes_reasoning():
    case = _case("fruit-shop")
    concepts = _valid_concepts()
    decision = _valid_decision()
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(concepts, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_CONCEPT_REASONING"},
            ),
            AIMessage(
                content=json.dumps(decision, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_DECISION_REASONING"},
            ),
        ]
    )

    result = asyncio.run(run_concept_bottleneck_case(model=model, model_name="test-model", case=case))

    assert result["concept_bottleneck"] == concepts
    assert result["world_decision"] == decision
    assert result["automatic_review"]["status"] == "passed"
    assert result["provider_calls"] == 2
    second_payload = json.loads(model.calls[1][1].content)
    assert second_payload["concept_bottleneck"] == concepts
    serialized = json.dumps(result, ensure_ascii=False)
    assert "PRIVATE_CONCEPT_REASONING" not in serialized
    assert "PRIVATE_DECISION_REASONING" not in serialized
    assert len(result["provider_reasoning_sha256"]) == 64


def test_schema_repairs_cannot_receive_hidden_business_labels():
    case = _case("fruit-shop")
    concepts = _valid_concepts()
    decision = _valid_decision()
    model = FakeModel(
        [
            AIMessage(content=json.dumps({**concepts, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(concepts, ensure_ascii=False)),
            AIMessage(content=json.dumps({**decision, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(decision, ensure_ascii=False)),
        ]
    )

    result = asyncio.run(
        run_concept_bottleneck_case(
            model=model,
            model_name="test-model",
            case=case,
            max_concept_repair_calls=1,
            max_decision_repair_calls=1,
        )
    )

    assert result["stage_repairs"] == {"concept": 1, "decision": 1}
    for repair_call in (model.calls[1], model.calls[3]):
        repair_prompt = repair_call[-1].content
        assert "只修复 JSON 契约" in repair_prompt
        assert "不要重新做业务判断" in repair_prompt
        assert "水果" not in repair_prompt


def test_call_budget_matches_the_two_step_baseline_and_has_no_model_judge():
    assert calculate_primary_call_count(case_count=6, model_count=1) == 12
    assert (
        calculate_provider_call_budget(
            primary_calls=12,
            max_concept_repair_calls=1,
            max_decision_repair_calls=1,
        )
        == 14
    )
