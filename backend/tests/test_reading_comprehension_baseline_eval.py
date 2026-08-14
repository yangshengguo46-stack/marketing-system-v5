from __future__ import annotations

import asyncio
import json
from argparse import Namespace
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from scripts.run_reading_comprehension_baseline_eval import (
    ARMS,
    BASELINE_METHOD_SHA256,
    CANDIDATE_METHOD_TEXT,
    FROZEN_MODEL,
    SHARED_OUTPUT_CONTRACT,
    action_relation_matches,
    build_arm_messages,
    build_blind_review_packet,
    calculate_primary_call_count,
    calculate_provider_call_budget,
    default_reading_cases,
    parse_reading_topic_record,
    review_reading_output,
    run_arm_case,
    run_evaluation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SKILL_PATH = REPO_ROOT / "backend" / "experiments" / "e38_topic_bridge" / "generate-content-topic" / "SKILL.md"
CANDIDATE_SKILL_PATH = REPO_ROOT / "backend" / "experiments" / "e39_reading_comprehension" / "read-before-topic" / "SKILL.md"


def _case(case_id: str):
    return next(item for item in default_reading_cases() if item.case_id == case_id)


def _valid_payload(case_id: str = "yellow-wallpaper") -> dict[str, object]:
    case = _case(case_id)
    evidence_ids = [item.evidence_id for item in case.evidence]
    first_evidence = evidence_ids[0]
    return {
        "supplied_path": [{"from": edge.from_node, "relation": edge.relation, "to": edge.to_node} for edge in case.supplied_path],
        "source_observations": [
            {
                "id": "o1",
                "claim": "来源直接记录了一个行为。",
                "evidence_refs": [first_evidence],
            }
        ],
        "action_relations": [
            {
                "actor": "叙述者",
                "action": "撕下",
                "target": "墙纸",
                "evidence_refs": [evidence_ids[-1]],
            }
        ],
        "state_changes": [],
        "derived_interpretations": [
            {
                "claim": "物件承载了人物处境的变化。",
                "based_on_observation_ids": ["o1"],
                "limitations": "这是文本解释，不是作者自述。",
            }
        ],
        "topic_brief": {
            "question": "这个物件如何参与人物处境的变化？",
            "central_claim": "它是限制与挣脱发生冲突的物质焦点。",
            "mechanism": "人物先被限制，随后通过撕下墙纸表达挣脱。",
            "counterpoint": "证据不能证明墙纸是疾病的客观原因。",
            "evidence_refs": evidence_ids,
        },
        "unknowns": ["作者本人是否如此解释仍未知。"],
    }


class _ReasoningModel:
    async def ainvoke(self, messages):
        del messages
        return AIMessage(
            content=json.dumps(_valid_payload(), ensure_ascii=False),
            additional_kwargs={"reasoning_content": "private chain of thought"},
            usage_metadata={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        )


def test_baseline_is_the_frozen_e38_skill_and_candidate_is_isolated() -> None:
    import hashlib

    assert BASELINE_SKILL_PATH.is_file()
    assert hashlib.sha256(BASELINE_SKILL_PATH.read_bytes()).hexdigest() == BASELINE_METHOD_SHA256
    assert BASELINE_METHOD_SHA256 == "29c5a762d1d35f1d86a15b6b068e5ccf1c5d132c9ae766a174113cfced7fea6d"
    assert CANDIDATE_SKILL_PATH.is_file()
    assert (CANDIDATE_SKILL_PATH.parent / "agents" / "openai.yaml").is_file()
    assert REPO_ROOT / "skills" / "public" not in CANDIDATE_SKILL_PATH.parents


def test_candidate_method_exposes_reading_layers_without_case_examples() -> None:
    for required in (
        "字面阅读",
        "关系阅读",
        "解释阅读",
        "选题收敛",
        "谁对谁做了什么",
        "来源观察",
        "解释不是来源事实",
        "反向解释",
    ):
        assert required in CANDIDATE_METHOD_TEXT

    for forbidden in (
        "水果",
        "黄金礼品",
        "海鲜",
        "火锅",
        "腕表",
        "医美",
        "黄色墙纸",
        "尤利西斯",
        "火柴",
        "CFC",
        "蒙特利尔",
        "自行车",
        "旧照片",
    ):
        assert forbidden not in CANDIDATE_METHOD_TEXT


def test_both_arms_share_contract_input_and_call_count() -> None:
    case = _case("matchgirls-strike")
    baseline = build_arm_messages(case=case, arm="baseline")
    candidate = build_arm_messages(case=case, arm="candidate")

    assert SHARED_OUTPUT_CONTRACT in str(baseline[0].content)
    assert SHARED_OUTPUT_CONTRACT in str(candidate[0].content)
    assert baseline[1].content == candidate[1].content
    assert len(baseline) == len(candidate) == 2
    assert calculate_primary_call_count(case_count=6, arm_count=len(ARMS), model_count=1) == 12
    assert (
        calculate_provider_call_budget(
            primary_calls=12,
            max_baseline_repairs=1,
            max_candidate_repairs=1,
        )
        == 14
    )


def test_six_cases_are_new_unique_and_keep_user_material_distinct() -> None:
    cases = default_reading_cases()
    assert [item.case_id for item in cases] == [
        "yellow-wallpaper",
        "shakespeare-and-company",
        "matchgirls-strike",
        "cfc-ozone-transition",
        "safety-bicycle-women",
        "old-photo-seam",
    ]
    assert len({item.case_id for item in cases}) == 6
    assert all(item.review_status == "preregistered_system_hypothesis" for item in cases)
    old_photo = _case("old-photo-seam")
    assert {item.source_kind for item in old_photo.evidence} == {"user_material"}
    assert all(item.source_url is None for item in old_photo.evidence)


def test_hidden_expectations_never_enter_model_messages() -> None:
    case = _case("cfc-ozone-transition")
    serialized = "\n".join(str(message.content) for arm in ARMS for message in build_arm_messages(case=case, arm=arm))
    for hidden_name in (
        "expected_actions",
        "semantic_groups",
        "required_topic_evidence",
        "preregistered_system_hypothesis",
        "safety solution",
    ):
        assert hidden_name not in serialized


def test_parser_preserves_exact_path_and_allows_empty_reading_lists() -> None:
    case = _case("yellow-wallpaper")
    payload = _valid_payload()
    payload["action_relations"] = []
    payload["state_changes"] = []
    payload["derived_interpretations"] = []
    parsed = parse_reading_topic_record(
        json.dumps(payload, ensure_ascii=False),
        case=case,
    )
    assert parsed["supplied_path"] == payload["supplied_path"]
    assert parsed["action_relations"] == []

    payload["supplied_path"][0]["relation"] = "导致"
    with pytest.raises(ValueError, match="supplied_path must exactly match"):
        parse_reading_topic_record(json.dumps(payload, ensure_ascii=False), case=case)


def test_parser_rejects_unknown_refs_duplicate_ids_and_contract_extras() -> None:
    case = _case("yellow-wallpaper")

    unknown_evidence = _valid_payload()
    unknown_evidence["topic_brief"]["evidence_refs"] = ["outside-pack"]
    with pytest.raises(ValueError, match="unknown evidence"):
        parse_reading_topic_record(json.dumps(unknown_evidence, ensure_ascii=False), case=case)

    duplicate = _valid_payload()
    duplicate["source_observations"].append(duplicate["source_observations"][0])
    with pytest.raises(ValueError, match="observation ids must be unique"):
        parse_reading_topic_record(json.dumps(duplicate, ensure_ascii=False), case=case)

    missing_observation = _valid_payload()
    missing_observation["derived_interpretations"][0]["based_on_observation_ids"] = ["missing"]
    with pytest.raises(ValueError, match="unknown observation"):
        parse_reading_topic_record(json.dumps(missing_observation, ensure_ascii=False), case=case)

    scored = _valid_payload()
    scored["topic_brief"]["score"] = 90
    with pytest.raises(ValueError, match="topic_brief must contain exactly"):
        parse_reading_topic_record(json.dumps(scored, ensure_ascii=False), case=case)


def test_action_matching_keeps_actor_action_and_target_in_their_own_fields() -> None:
    expected = _case("matchgirls-strike").acceptance.expected_actions[1]
    correct = {
        "actor": "约1400名女工",
        "action": "集体离岗并开始罢工",
        "target": "工厂管理层",
    }
    reversed_roles = {
        "actor": "工厂管理层",
        "action": "集体罢工",
        "target": "女工",
    }
    wrong_target = {
        "actor": "女工",
        "action": "罢工",
        "target": "火柴",
    }
    assert action_relation_matches(correct, expected)
    assert not action_relation_matches(reversed_roles, expected)
    assert not action_relation_matches(wrong_target, expected)


def test_automatic_review_scores_topic_semantics_only_from_topic_fields() -> None:
    case = _case("yellow-wallpaper")
    payload = _valid_payload()
    payload["source_observations"][0]["claim"] = "限制、感知、挣脱、物质焦点"
    payload["topic_brief"] = {
        "question": "发生了什么？",
        "central_claim": "资料值得讨论。",
        "mechanism": "多个事实彼此相关。",
        "counterpoint": "仍有未知。",
        "evidence_refs": [item.evidence_id for item in case.evidence],
    }
    parsed = parse_reading_topic_record(json.dumps(payload, ensure_ascii=False), case=case)
    review = review_reading_output(output=parsed, case=case)
    assert review["semantic_groups_hit"] == 0
    assert review["required_topic_evidence_passed"] is True


def test_reasoning_content_is_hashed_but_never_persisted_in_record() -> None:
    record = asyncio.run(
        run_arm_case(
            model=_ReasoningModel(),
            model_name=FROZEN_MODEL,
            case=_case("yellow-wallpaper"),
            arm="candidate",
        )
    )
    serialized = json.dumps(record, ensure_ascii=False)
    assert record["provider_reasoning_present"] is True
    assert record["provider_reasoning_sha256"]
    assert "private chain of thought" not in serialized
    assert "reasoning_content" not in serialized


def test_blind_review_packet_hides_arm_and_keeps_key_separate() -> None:
    records = [
        {
            "case_id": "yellow-wallpaper",
            "arm": arm,
            "reading_output": _valid_payload(),
            "usage": {"total_tokens": 1},
        }
        for arm in ARMS
    ]
    packet, key = build_blind_review_packet(records=records, seed=80)
    assert len(packet["items"]) == len(key["items"]) == 2
    assert "baseline" not in json.dumps(packet, ensure_ascii=False)
    assert "candidate" not in json.dumps(packet, ensure_ascii=False)
    assert {item["arm"] for item in key["items"]} == set(ARMS)


def test_live_runner_rejects_non_frozen_models_before_provider_access(tmp_path: Path) -> None:
    args = Namespace(
        execute=True,
        models=["unfrozen-model"],
        case_ids=[],
        max_calls=12,
        max_baseline_repair_calls=1,
        max_candidate_repair_calls=1,
        seed=80,
        blind_seed=56,
        output_root=tmp_path,
        run_id="must-not-run",
    )
    assert FROZEN_MODEL == "glm-5-2-260617"
    with pytest.raises(ValueError, match="frozen model"):
        asyncio.run(run_evaluation(args))
