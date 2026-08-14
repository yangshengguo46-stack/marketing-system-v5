from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.run_root_to_topic_combination_probe import (
    DISCOVERY_METHOD_TEXT,
    FROZEN_MODEL,
    CigarLoungeAcceptance,
    SearchResult,
    build_discovery_messages,
    build_reading_case,
    build_search_evidence,
    parse_discovery_record,
    review_cigar_lounge_probe,
)

from scripts.run_reading_comprehension_baseline_eval import build_arm_messages

REPO_ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_SKILL_PATH = REPO_ROOT / "backend" / "experiments" / "e40_root_to_topic" / "discover-research-path" / "SKILL.md"


def _valid_discovery() -> dict[str, object]:
    return {
        "content_root": "雪茄",
        "candidate_paths": [
            {
                "id": "person-1",
                "axis": "人物",
                "entity": "某历史人物",
                "relation": "与雪茄形象形成长期公众关联",
                "why_worth_researching": "人物形象、公开记录与具体物件可能形成可核验选题。",
                "search_queries": ["某历史人物 雪茄 公开记录"],
            }
        ],
        "unknowns": ["具体偏好与照片中物件尚未核验。"],
    }


def test_e40_skill_is_isolated_and_contains_no_development_answers() -> None:
    assert DISCOVERY_SKILL_PATH.is_file()
    assert REPO_ROOT / "skills" / "public" not in DISCOVERY_SKILL_PATH.parents
    for required in (
        "命名候选",
        "检索词",
        "关系假设",
        "待核验",
        "不得重选内容根",
    ):
        assert required in DISCOVERY_METHOD_TEXT
    for forbidden in (
        "雪茄",
        "格瓦拉",
        "丘吉尔",
        "水果",
        "黄金礼品",
        "海鲜",
        "火锅",
        "腕表",
        "医美",
    ):
        assert forbidden not in DISCOVERY_METHOD_TEXT


def test_discovery_messages_do_not_include_hidden_acceptance() -> None:
    messages = build_discovery_messages(
        business_expression="我是开某专门馆的，该怎么起号？",
        content_root="某品类",
        map_axes=("种类与子世界", "时间与历史", "人物", "事件", "冲突"),
    )
    serialized = "\n".join(str(message.content) for message in messages)
    assert "某品类" in serialized
    for hidden in CigarLoungeAcceptance().all_hidden_terms:
        assert hidden not in serialized


def test_discovery_parser_binds_root_and_rejects_quota_or_fact_fields() -> None:
    parsed = parse_discovery_record(
        json.dumps(_valid_discovery(), ensure_ascii=False),
        expected_root="雪茄",
    )
    assert parsed["content_root"] == "雪茄"
    assert parsed["candidate_paths"][0]["id"] == "person-1"

    wrong_root = _valid_discovery()
    wrong_root["content_root"] = "咖啡馆"
    with pytest.raises(ValueError, match="content_root must match"):
        parse_discovery_record(json.dumps(wrong_root, ensure_ascii=False), expected_root="雪茄")

    extra_fact = _valid_discovery()
    extra_fact["candidate_paths"][0]["favorite_product"] = "未核验型号"
    with pytest.raises(ValueError, match=r"candidate_paths\[0\] must contain exactly"):
        parse_discovery_record(json.dumps(extra_fact, ensure_ascii=False), expected_root="雪茄")

    too_many = _valid_discovery()
    too_many["candidate_paths"] = [{**too_many["candidate_paths"][0], "id": f"p-{index}", "entity": f"候选{index}"} for index in range(9)]
    with pytest.raises(ValueError, match="at most 8"):
        parse_discovery_record(json.dumps(too_many, ensure_ascii=False), expected_root="雪茄")


def test_search_evidence_is_bounded_deduplicated_and_source_typed() -> None:
    results = [
        SearchResult(
            query="q1",
            title="A",
            url="https://example.com/a",
            snippet="x" * 900,
        ),
        SearchResult(
            query="q2",
            title="A duplicate",
            url="https://example.com/a",
            snippet="duplicate",
        ),
        SearchResult(
            query="q3",
            title="B",
            url="https://example.com/b",
            snippet="useful",
        ),
    ]
    evidence = build_search_evidence(results, max_items=2, max_claim_chars=500)
    assert len(evidence) == 2
    assert [item.evidence_id for item in evidence] == ["search-1", "search-2"]
    assert all(item.source_kind == "search_result_snippet" for item in evidence)
    assert len(evidence[0].claim) <= 500
    assert evidence[0].source_url == "https://example.com/a"


def test_reading_case_and_messages_preserve_selected_path_without_hidden_terms() -> None:
    discovery = parse_discovery_record(
        json.dumps(_valid_discovery(), ensure_ascii=False),
        expected_root="雪茄",
    )
    evidence = build_search_evidence(
        [
            SearchResult(
                query="q",
                title="公开资料",
                url="https://example.com/source",
                snippet="资料直接记录了人物与该品类的关联。",
            )
        ]
    )
    case = build_reading_case(
        business_expression="我是开雪茄馆的，该怎么起号？",
        content_root="雪茄",
        candidate=discovery["candidate_paths"][0],
        evidence=evidence,
    )
    assert case.supplied_path[0].from_node == "雪茄"
    assert case.supplied_path[0].relation == discovery["candidate_paths"][0]["relation"]
    assert case.supplied_path[0].to_node == "某历史人物"

    serialized = "\n".join(str(message.content) for message in build_arm_messages(case=case, arm="candidate"))
    assert "公开资料" in serialized
    for hidden in CigarLoungeAcceptance().all_hidden_terms:
        assert hidden not in serialized


def test_hidden_review_requires_recall_and_specific_topic_without_asserting_answer() -> None:
    acceptance = CigarLoungeAcceptance()
    discovery = {
        "candidate_paths": [
            {
                "entity": "Che Guevara",
            }
        ]
    }
    topic_outputs = [
        {
            "topic_brief": {
                "question": "切·格瓦拉在经典照片中叼的究竟是哪一款雪茄？",
                "central_claim": "公众形象与具体物件之间的差距可以成为可考证选题。",
                "mechanism": "先识别人物与影像，再核验物件品牌或型号。",
                "counterpoint": "当前搜索摘要不足以确认型号。",
                "evidence_refs": ["search-1"],
            },
            "source_observations": [],
            "action_relations": [],
            "state_changes": [],
            "derived_interpretations": [],
            "unknowns": ["具体型号未知。"],
        }
    ]
    review = review_cigar_lounge_probe(
        discovery=discovery,
        topic_outputs=topic_outputs,
        acceptance=acceptance,
    )
    assert review["target_person_recalled"] is True
    assert review["specific_topic_generated"] is True
    assert review["unsupported_specific_answer"] is False
    assert review["passed"] is True

    asserted = json.loads(json.dumps(topic_outputs, ensure_ascii=False))
    asserted[0]["topic_brief"]["central_claim"] = "照片中确定是某型号雪茄。"
    asserted_review = review_cigar_lounge_probe(
        discovery=discovery,
        topic_outputs=asserted,
        acceptance=acceptance,
    )
    assert asserted_review["unsupported_specific_answer"] is True
    assert asserted_review["passed"] is False


def test_probe_model_is_frozen() -> None:
    assert FROZEN_MODEL == "glm-5-2-260617"
