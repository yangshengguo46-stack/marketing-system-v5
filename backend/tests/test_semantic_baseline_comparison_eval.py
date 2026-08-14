from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest
from scripts.run_semantic_baseline_comparison_eval import (
    BASELINE_COMMIT,
    BASELINE_PROMPT_SHA256,
    CANDIDATE_SYSTEM_PROMPT,
    FROZEN_MODEL,
    build_baseline_messages,
    build_candidate_messages,
    calculate_primary_call_count,
    calculate_provider_call_budget,
    canonical_term,
    default_comparison_cases,
    matches_exact_alias,
    parse_candidate_structure,
    review_arm_output,
    run_evaluation,
)

from scripts.run_account_content_structure_eval import ACCOUNT_CONTENT_STRUCTURE_SYSTEM_PROMPT


def _case(case_id: str):
    return next(item for item in default_comparison_cases() if item.case_id == case_id)


def _candidate_payload() -> dict[str, object]:
    return {
        "source_object": {
            "term": "淡水钓鱼饵料",
            "basis": "用户明确销售的商品",
            "evidence_refs": ["business-1"],
        },
        "root_candidates": [
            {
                "id": "fishing",
                "term": "淡水钓鱼",
                "root_kind": "practice_or_need",
                "derivation": "饵料直接用于完成淡水钓鱼",
                "capacity_axes": ["对象", "时间", "地点", "人物", "事件与冲突"],
                "business_return_path": "钓鱼中的饵料选择可回到商品",
                "conditions": [],
                "risks": [],
                "evidence_refs": ["business-1"],
            },
            {
                "id": "bait",
                "term": "钓鱼饵料",
                "root_kind": "object",
                "derivation": "这是直接商品",
                "capacity_axes": ["类型", "使用"],
                "business_return_path": "直接回到商品",
                "conditions": [],
                "risks": ["可能停在中间物"],
                "evidence_refs": ["business-1"],
            },
        ],
        "object_world": {
            "selected_candidate_id": "fishing",
            "acceptable_alternative_ids": [],
            "reason": "钓鱼是饵料完成的更完整世界",
        },
        "audience_world": {
            "selected_candidate_id": "fishing",
            "acceptable_alternative_ids": ["bait"],
            "reason": "观众长期进入钓鱼，饵料仍是近端替代",
        },
        "unknowns": [],
    }


def test_baseline_is_exactly_the_user_requested_ca2af9f8_version():
    assert BASELINE_COMMIT == "ca2af9f8905698a0ad81a204350afa07fb840bcf"
    assert BASELINE_PROMPT_SHA256 == "96fb4ad3c50c349d6b641a61730b7bb2c06dfec2807718f7e124480d93ae873d"
    assert "原始业务对象" in ACCOUNT_CONTENT_STRUCTURE_SYSTEM_PROMPT
    assert "观众内容世界" in ACCOUNT_CONTENT_STRUCTURE_SYSTEM_PROMPT
    assert "内容发动机" in ACCOUNT_CONTENT_STRUCTURE_SYSTEM_PROMPT
    assert "注意力入口" in ACCOUNT_CONTENT_STRUCTURE_SYSTEM_PROMPT


def test_candidate_prompt_is_example_free_and_uses_plain_attention_shifts():
    for required in (
        "从名词看动作",
        "从产品看用途",
        "从用途看长期需求",
        "对象世界",
        "观众世界",
        "允许相同",
        "允许不同",
        "不是固定分类",
    ):
        assert required in CANDIDATE_SYSTEM_PROMPT

    for forbidden in (
        "Qualia",
        "JTBD",
        "concept bottleneck",
        "complete_object",
        "seller_operation_or_proof",
        "buyer_ordinary_use",
        "buyer_social_practice_or_result",
        "水果",
        "黄金礼品",
        "海鲜",
        "火锅",
        "腕表",
        "医美",
        "茶叶",
        "咖喱",
        "面包",
        "退休纪念",
        "陶瓷",
        "月饼",
        "儿童图书",
        "皮鞋",
        "婚礼请柬",
        "饺子",
        "观赏鱼",
        "钓鱼",
        "烘焙",
        "生日蛋糕",
        "古籍",
        "宠物告别",
    ):
        assert forbidden not in CANDIDATE_SYSTEM_PROMPT


def test_six_new_cases_are_unique_and_not_prior_development_examples():
    cases = default_comparison_cases()
    assert [item.case_id for item in cases] == [
        "ornamental-fish-shop",
        "freshwater-fishing-bait",
        "baking-molds",
        "birthday-cakes",
        "ancient-book-restoration",
        "pet-farewell-service",
    ]
    assert all(item.review_status == "preregistered_system_hypothesis" for item in cases)
    assert len({item.case_id for item in cases}) == 6


def test_hidden_acceptance_never_enters_either_arm_messages():
    case = _case("freshwater-fishing-bait")
    messages = [*build_baseline_messages(case=case), *build_candidate_messages(case=case)]
    serialized = "\n".join(str(message.content) for message in messages)
    for hidden_key in (
        "acceptance",
        "source_aliases",
        "object_preferred_aliases",
        "object_acceptable_aliases",
        "audience_preferred_aliases",
        "audience_acceptable_aliases",
        "example_preferred",
    ):
        assert hidden_key not in serialized
    assert "淡水垂钓金标" not in serialized


def test_candidate_parser_binds_selected_terms_to_known_candidate_ids():
    parsed = parse_candidate_structure(json.dumps(_candidate_payload(), ensure_ascii=False))
    assert parsed["object_world"]["term"] == "淡水钓鱼"
    assert parsed["audience_world"]["term"] == "淡水钓鱼"
    assert parsed["audience_world"]["acceptable_alternatives"] == [{"candidate_id": "bait", "term": "钓鱼饵料", "root_kind": "object"}]

    unknown = _candidate_payload()
    unknown["audience_world"] = {
        **unknown["audience_world"],
        "selected_candidate_id": "missing",
    }
    with pytest.raises(ValueError, match="known candidate"):
        parse_candidate_structure(json.dumps(unknown, ensure_ascii=False))

    overlap = _candidate_payload()
    overlap["object_world"] = {
        **overlap["object_world"],
        "acceptable_alternative_ids": ["fishing"],
    }
    with pytest.raises(ValueError, match="must not include the selected"):
        parse_candidate_structure(json.dumps(overlap, ensure_ascii=False))


def test_candidate_parser_rejects_scores_and_unknown_evidence_refs():
    scored = _candidate_payload()
    scored["root_candidates"][0]["score"] = 90
    with pytest.raises(ValueError, match="root candidate"):
        parse_candidate_structure(json.dumps(scored, ensure_ascii=False))

    unknown_ref = _candidate_payload()
    unknown_ref["source_object"]["evidence_refs"] = ["hidden-gold"]
    with pytest.raises(ValueError, match="unknown evidence"):
        parse_candidate_structure(
            json.dumps(unknown_ref, ensure_ascii=False),
            allowed_evidence_ids={"business-1"},
        )


def test_exact_alias_matching_does_not_repeat_parent_child_substring_bug():
    assert canonical_term("淡水钓鱼内容世界") == "淡水钓鱼"
    assert matches_exact_alias("淡水钓鱼内容世界", ("淡水钓鱼", "淡水垂钓"))
    assert not matches_exact_alias("淡水钓鱼饵料", ("淡水钓鱼", "淡水垂钓"))
    assert not matches_exact_alias("饺子馅料", ("饺子",))


def test_common_review_distinguishes_preferred_acceptable_and_unavailable_scope():
    case = _case("freshwater-fishing-bait")
    candidate = parse_candidate_structure(json.dumps(_candidate_payload(), ensure_ascii=False))
    candidate_review = review_arm_output(arm="candidate", output=candidate, case=case)
    assert candidate_review["source_object"] == "passed"
    assert candidate_review["object_world"] == "preferred"
    assert candidate_review["audience_world"] == "preferred"
    assert candidate_review["candidate_recall"] == "passed"

    baseline = {
        "source_object": {"term": "淡水钓鱼饵料"},
        "audience_world": {"term": "钓鱼饵料"},
    }
    baseline_review = review_arm_output(arm="baseline", output=baseline, case=case)
    assert baseline_review["source_object"] == "passed"
    assert baseline_review["object_world"] == "not_available"
    assert baseline_review["audience_world"] == "failed"
    assert baseline_review["candidate_recall"] == "not_available"


def test_comparison_call_budget_is_six_cases_times_two_equal_arms_plus_two_repairs():
    assert calculate_primary_call_count(case_count=6, arm_count=2, model_count=1) == 12
    assert calculate_provider_call_budget(primary_calls=12, max_baseline_repairs=1, max_candidate_repairs=1) == 14


def test_live_runner_rejects_non_frozen_models_before_accessing_provider(tmp_path: Path):
    args = Namespace(
        execute=True,
        models=["unfrozen-model"],
        case_ids=[],
        max_calls=12,
        max_baseline_repair_calls=1,
        max_candidate_repair_calls=1,
        seed=80,
        output_root=tmp_path,
        run_id="must-not-run",
    )
    assert FROZEN_MODEL == "glm-5-2-260617"
    with pytest.raises(ValueError, match="frozen model"):
        import asyncio

        asyncio.run(run_evaluation(args))
