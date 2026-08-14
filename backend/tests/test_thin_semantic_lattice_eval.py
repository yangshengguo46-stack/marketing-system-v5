from __future__ import annotations

import asyncio
import json
from argparse import Namespace
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from scripts.run_thin_semantic_lattice_eval import (
    CANDIDATE_SYSTEM_PROMPT,
    DECISION_SYSTEM_PROMPT,
    FROZEN_MODEL,
    build_candidate_messages,
    build_decision_messages,
    calculate_primary_call_count,
    calculate_provider_call_budget,
    default_contrast_expectations,
    default_thin_lattice_cases,
    parse_thin_lattice,
    parse_world_decision,
    review_contrast_pairs,
    review_thin_lattice_result,
    run_evaluation,
    run_thin_lattice_case,
)


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def _case(case_id: str):
    return next(case for case in default_thin_lattice_cases() if case.case_id == case_id)


def _valid_lattice() -> dict[str, object]:
    return {
        "source_object": "银质商务礼品",
        "direct_use": "商务关系中送礼",
        "practice_or_result": "商务赠礼",
        "return_path": "赠礼内容中的礼品选择可直接回到银质商务礼品",
        "over_abstraction_risk": "人情世界过宽，可能失去商务赠礼返回路径",
        "candidate_roots": [
            {
                "id": "root-gifting",
                "term": "商务赠礼",
                "root_kind": "activity_or_practice",
                "why_complete": "它有参与者、场合、选择和关系后果",
                "return_path": "内容中的礼品选择回到原商品",
                "overreach_risk": "扩大到泛人情会脱离商务礼品",
            }
        ],
        "unknowns": [],
    }


def _valid_decision() -> dict[str, object]:
    return {
        "source_object": "银质商务礼品",
        "audience_world": "商务赠礼",
        "world_kind": "activity_or_practice",
        "selected_candidate_id": "root-gifting",
        "candidate_relation": "selected_candidate",
        "reason": "材质可替换，而赠礼用途组织了更完整的内容世界",
        "return_path": "送礼场合和选择会自然回到商务礼品",
        "unknowns": [],
    }


def test_prompts_keep_only_a_plain_language_thin_lattice():
    for required in ("来源对象", "直接用途", "实践或结果", "回到原业务", "过度抽象"):
        assert required in CANDIDATE_SYSTEM_PROMPT
    assert "允许纠正" in DECISION_SYSTEM_PROMPT

    prompts = CANDIDATE_SYSTEM_PROMPT + DECISION_SYSTEM_PROMPT
    for theory_term in (
        "Qualia",
        "Formal",
        "Constitutive",
        "Agentive",
        "Telic",
        "JTBD",
        "Jobs-to-be-Done",
        "frame semantics",
        "concept bottleneck",
        "社会实践理论",
        "功能进展",
        "情绪进展",
        "社会进展",
    ):
        assert theory_term not in prompts

    for held_out_term in ("茶叶", "银质", "木质", "银饰", "咖喱"):
        assert held_out_term not in prompts
    for old_case_term in ("黄金礼品", "水果店", "海鲜", "火锅底料", "腕表", "医美"):
        assert old_case_term not in prompts


def test_seven_new_cases_and_four_contrasts_are_frozen_without_old_cases():
    cases = default_thin_lattice_cases()
    assert [case.case_id for case in cases] == [
        "tea-shop-container",
        "tea-direct-product",
        "silver-business-gift",
        "wood-business-gift",
        "silver-jewelry",
        "japanese-curry-block",
        "thai-curry-sauce",
    ]
    assert len(default_contrast_expectations()) == 4
    old_ids = {
        "gold-gift",
        "fruit-shop",
        "seafood-source",
        "chongqing-hotpot-base",
        "watch-account",
        "medical-aesthetics-account",
    }
    assert old_ids.isdisjoint(case.case_id for case in cases)


def test_hidden_acceptance_and_contrasts_never_enter_model_messages():
    case = _case("silver-business-gift")
    messages = [
        *build_candidate_messages(case=case),
        *build_decision_messages(case=case, lattice=_valid_lattice()),
    ]
    payload = "\n".join(str(message.content) for message in messages)

    for hidden_key in (
        "acceptance",
        "source_signal_groups",
        "world_signal_groups",
        "forbidden_world_signals",
        "expected_world_kind",
        "contrast_id",
        "material_invariance",
    ):
        assert hidden_key not in payload
    assert "作为礼品赠送" not in payload


def test_lattice_parser_allows_unknown_and_empty_candidates():
    payload = {
        "source_object": None,
        "direct_use": None,
        "practice_or_result": None,
        "return_path": None,
        "over_abstraction_risk": None,
        "candidate_roots": [],
        "unknowns": [],
    }
    assert parse_thin_lattice(json.dumps(payload, ensure_ascii=False)) == payload


def test_lattice_parser_rejects_numeric_shortcuts_and_extra_fields():
    with pytest.raises(ValueError, match="direct_use"):
        parse_thin_lattice(json.dumps({**_valid_lattice(), "direct_use": 0.8}, ensure_ascii=False))

    candidate = dict(_valid_lattice()["candidate_roots"][0])
    candidate["score"] = 90
    with pytest.raises(ValueError, match="candidate root"):
        parse_thin_lattice(json.dumps({**_valid_lattice(), "candidate_roots": [candidate]}, ensure_ascii=False))


def test_decision_can_select_or_correct_without_being_bound_to_candidates():
    lattice = parse_thin_lattice(json.dumps(_valid_lattice(), ensure_ascii=False))
    selected = parse_world_decision(json.dumps(_valid_decision(), ensure_ascii=False), lattice=lattice)
    assert selected["selected_candidate_id"] == "root-gifting"

    corrected_payload = {
        **_valid_decision(),
        "audience_world": "赠礼",
        "selected_candidate_id": None,
        "candidate_relation": "corrected_candidate",
    }
    corrected = parse_world_decision(json.dumps(corrected_payload, ensure_ascii=False), lattice=lattice)
    assert corrected["candidate_relation"] == "corrected_candidate"

    with pytest.raises(ValueError, match="known candidate"):
        parse_world_decision(
            json.dumps({**_valid_decision(), "selected_candidate_id": "missing"}, ensure_ascii=False),
            lattice=lattice,
        )


def test_hidden_review_separates_candidate_recall_from_final_convergence():
    case = _case("silver-business-gift")
    lattice = {**_valid_lattice(), "candidate_roots": []}
    decision = {
        **_valid_decision(),
        "audience_world": "赠礼",
        "selected_candidate_id": None,
        "candidate_relation": "corrected_candidate",
    }

    review = review_thin_lattice_result(lattice=lattice, decision=decision, case=case)

    assert review["candidate_recall"] == "failed"
    assert review["final_convergence"] == "passed"
    assert review["status"] == "failed_business"


def test_contrast_review_checks_invariance_and_use_sensitivity():
    records = []
    for case in default_thin_lattice_cases():
        root = case.acceptance.example_passing_world
        records.append(
            {
                "case_id": case.case_id,
                "world_decision": {
                    "audience_world": root,
                    "world_kind": case.acceptance.expected_world_kind,
                },
                "automatic_review": {"final_convergence": "passed"},
            }
        )

    reviews = review_contrast_pairs(records, expectations=default_contrast_expectations())
    assert {review["status"] for review in reviews} == {"passed"}

    broken = [dict(record) for record in records]
    jewelry = next(record for record in broken if record["case_id"] == "silver-jewelry")
    jewelry["world_decision"] = {"audience_world": "赠礼", "world_kind": "activity_or_practice"}
    jewelry["automatic_review"] = {"final_convergence": "failed"}
    broken_reviews = review_contrast_pairs(broken, expectations=default_contrast_expectations())
    use_review = next(review for review in broken_reviews if review["contrast_id"] == "same-material-different-use")
    assert use_review["status"] == "failed"


def test_case_run_passes_only_the_thin_lattice_and_hashes_reasoning():
    case = _case("silver-business-gift")
    lattice = _valid_lattice()
    decision = _valid_decision()
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(lattice, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_LATTICE_REASONING"},
            ),
            AIMessage(
                content=json.dumps(decision, ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_DECISION_REASONING"},
            ),
        ]
    )

    result = asyncio.run(run_thin_lattice_case(model=model, model_name="test-model", case=case))

    assert result["thin_lattice"] == lattice
    assert result["world_decision"] == decision
    assert result["automatic_review"]["status"] == "passed"
    assert result["provider_calls"] == 2
    second_payload = json.loads(model.calls[1][1].content)
    assert second_payload["thin_lattice"] == lattice
    serialized = json.dumps(result, ensure_ascii=False)
    assert "PRIVATE_LATTICE_REASONING" not in serialized
    assert "PRIVATE_DECISION_REASONING" not in serialized
    assert len(result["provider_reasoning_sha256"]) == 64


def test_schema_repairs_receive_only_contract_errors_not_hidden_labels():
    case = _case("silver-business-gift")
    lattice = _valid_lattice()
    decision = _valid_decision()
    model = FakeModel(
        [
            AIMessage(content=json.dumps({**lattice, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(lattice, ensure_ascii=False)),
            AIMessage(content=json.dumps({**decision, "extra": True}, ensure_ascii=False)),
            AIMessage(content=json.dumps(decision, ensure_ascii=False)),
        ]
    )

    result = asyncio.run(
        run_thin_lattice_case(
            model=model,
            model_name="test-model",
            case=case,
            max_candidate_repair_calls=1,
            max_decision_repair_calls=1,
        )
    )

    assert result["stage_repairs"] == {"candidate": 1, "decision": 1}
    for repair_call in (model.calls[1], model.calls[3]):
        repair_prompt = repair_call[-1].content
        assert "只修复 JSON 契约" in repair_prompt
        assert "不要重新做业务判断" in repair_prompt
        assert "赠礼" not in repair_prompt
        assert "银质商务礼品" not in repair_prompt


def test_call_budget_is_sealed_for_seven_two_call_cases_without_a_model_judge():
    assert calculate_primary_call_count(case_count=7, model_count=1) == 14
    assert (
        calculate_provider_call_budget(
            primary_calls=14,
            max_candidate_repair_calls=1,
            max_decision_repair_calls=1,
        )
        == 16
    )


def test_live_runner_rejects_any_model_outside_the_preregistered_single_model(tmp_path: Path):
    args = Namespace(
        execute=True,
        models=["unfrozen-model"],
        case_ids=[],
        max_calls=14,
        max_candidate_repair_calls=1,
        max_decision_repair_calls=1,
        seed=80,
        output_root=tmp_path,
        run_id="must-not-run",
    )
    assert FROZEN_MODEL == "glm-5-2-260617"
    with pytest.raises(ValueError, match="frozen model"):
        asyncio.run(run_evaluation(args))
