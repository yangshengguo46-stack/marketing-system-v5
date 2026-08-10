from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from mcn_incubation.knowledge import (
    MCN_GATEKEEPING_RESEARCH_SOURCE_ID,
    XHS_MCN_INTRO_SOURCE_ID,
    default_knowledge_catalog,
)
from mcn_incubation.methods import default_method_library

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
