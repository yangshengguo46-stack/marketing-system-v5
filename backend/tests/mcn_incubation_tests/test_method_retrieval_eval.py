from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from mcn_incubation.knowledge import (
    MCN_GATEKEEPING_RESEARCH_SOURCE_ID,
    XHS_MCN_INTRO_SOURCE_ID,
    default_knowledge_catalog,
)
from mcn_incubation.methods import default_method_cards, default_method_library

REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "method-retrieval-eval.jsonl"


def _load_cases() -> list[dict]:
    return [json.loads(line) for line in EVAL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_method_retrieval_eval_covers_distinct_incubation_questions_without_full_dump() -> None:
    library = default_method_library()
    cases = _load_cases()

    assert len(cases) >= 12
    assert len({case["case_id"] for case in cases}) == len(cases)
    for case in cases:
        selected = library.search(query=case["query"], limit=case["limit"])
        capabilities = {card.capability for card in selected}
        assert set(case["expected_capabilities"]).issubset(capabilities), case["case_id"]
        assert len(selected) <= case["limit"]
        assert len(selected) < len(library.cards)
        for card in selected:
            library.source_catalog.resolve(card.source_refs)


def test_time_sensitive_platform_source_becomes_refresh_due_without_retiring_research() -> None:
    catalog = default_knowledge_catalog()
    as_of = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)

    assert catalog.get(XHS_MCN_INTRO_SOURCE_ID).is_refresh_due(as_of=as_of)
    assert not catalog.get(MCN_GATEKEEPING_RESEARCH_SOURCE_ID).is_refresh_due(as_of=as_of)


def test_m01_observed_failures_are_source_backed_method_boundaries_not_prompt_gates() -> None:
    cards = {card.method_card_id: card for card in default_method_cards()}
    source_id = "V5:docs/mcn-incubation-v5/evidence/2026-08-11-m01-agent-evaluation.md"

    expression_text = " ".join((*cards["expression-form-v1"].lens, *cards["expression-form-v1"].counterexamples))
    content_text = " ".join((*cards["content-engine-v1"].lens, *cards["content-engine-v1"].counterexamples))
    experiment_text = " ".join((*cards["experiment-design-v1"].lens, *cards["experiment-design-v1"].counterexamples))

    assert "镜头意愿" in expression_text
    assert "从业年限" in content_text and "可公开案例" in content_text
    assert "曝光" in experiment_text and "付费需求" in experiment_text
    assert all(
        source_id in cards[card_id].source_refs
        for card_id in (
            "expression-form-v1",
            "content-engine-v1",
            "experiment-design-v1",
        )
    )
    assert default_method_library().source_catalog.get(source_id).source_id == source_id


def test_xiaohongshu_mcn_definition_cannot_support_platform_fit_or_audience_claims() -> None:
    source = default_knowledge_catalog().get(XHS_MCN_INTRO_SOURCE_ID)
    limitations = " ".join(source.limitations)

    assert "audience composition" in limitations
    assert "platform fit" in limitations
    assert "platform priority" in limitations
