from __future__ import annotations

from dataclasses import replace

import pytest
from scripts.marketing_semantic_annotation_protocol import (
    MarketingSemanticAnnotation,
    ScopeDecision,
    annotation_fingerprint,
    default_development_annotations,
    validate_annotation,
)


def _annotation(case_id: str) -> MarketingSemanticAnnotation:
    return next(item for item in default_development_annotations() if item.case_id == case_id)


def test_six_user_corrected_cases_are_development_evidence_not_held_out_tests():
    annotations = default_development_annotations()
    assert [item.case_id for item in annotations] == [
        "fruit-shop",
        "gold-gift",
        "seafood-source",
        "chongqing-hotpot-base",
        "watch-business",
        "medical-aesthetics-business",
    ]
    assert all(item.review_status == "user_reviewed_development" for item in annotations)
    assert all(item.evidence_refs for item in annotations)
    assert all("held_out" not in item.review_status for item in annotations)


def test_protocol_separates_object_world_from_audience_world_and_allows_alternatives():
    for annotation in default_development_annotations():
        assert {decision.scope for decision in annotation.scope_decisions} == {
            "object_world",
            "audience_world",
        }
        candidate_ids = {candidate.candidate_id for candidate in annotation.candidates}
        for decision in annotation.scope_decisions:
            assert decision.preferred_candidate_ids
            assert set(decision.preferred_candidate_ids) <= candidate_ids
            assert set(decision.acceptable_candidate_ids) <= candidate_ids
            assert set(decision.rejected_candidate_ids) <= candidate_ids

    gold = _annotation("gold-gift")
    assert gold.decision("object_world").preferred_candidate_ids == ("gift-object",)
    assert gold.decision("audience_world").preferred_candidate_ids == ("gifting-practice",)
    assert "gift-object" in gold.decision("audience_world").acceptable_candidate_ids

    medical = _annotation("medical-aesthetics-business")
    assert medical.decision("object_world").preferred_candidate_ids == ("medical-aesthetics",)
    assert medical.decision("audience_world").preferred_candidate_ids == ("beauty",)


def test_object_and_intermediate_product_corrections_remain_explicit():
    assert _annotation("fruit-shop").decision("audience_world").preferred_candidate_ids == ("fruit",)
    assert _annotation("seafood-source").decision("audience_world").preferred_candidate_ids == ("seafood",)
    assert _annotation("watch-business").decision("audience_world").preferred_candidate_ids == ("watches",)

    hotpot = _annotation("chongqing-hotpot-base")
    assert hotpot.decision("object_world").preferred_candidate_ids == ("hotpot",)
    assert "hotpot-base" in hotpot.decision("object_world").rejected_candidate_ids


def test_every_preferred_candidate_has_capacity_and_a_business_return_path():
    for annotation in default_development_annotations():
        by_id = {candidate.candidate_id: candidate for candidate in annotation.candidates}
        preferred_ids = {candidate_id for decision in annotation.scope_decisions for candidate_id in decision.preferred_candidate_ids}
        for candidate_id in preferred_ids:
            candidate = by_id[candidate_id]
            assert candidate.capacity_axes
            assert candidate.business_return_path
            assert candidate.derivation


def test_protocol_does_not_mix_content_subjects_with_presentation_forms():
    serialized = repr(default_development_annotations())
    for presentation_term in ("口播", "微短剧", "情景剧", "图文", "Vlog", "直播"):
        assert presentation_term not in serialized


def test_validator_rejects_unknown_or_overlapping_decision_ids():
    annotation = _annotation("fruit-shop")
    bad_unknown = replace(
        annotation,
        scope_decisions=(
            replace(
                annotation.decision("object_world"),
                preferred_candidate_ids=("missing-candidate",),
            ),
            annotation.decision("audience_world"),
        ),
    )
    with pytest.raises(ValueError, match="unknown candidate ids"):
        validate_annotation(bad_unknown)

    audience = annotation.decision("audience_world")
    bad_overlap = replace(
        annotation,
        scope_decisions=(
            annotation.decision("object_world"),
            ScopeDecision(
                scope="audience_world",
                preferred_candidate_ids=audience.preferred_candidate_ids,
                acceptable_candidate_ids=audience.preferred_candidate_ids,
                rejected_candidate_ids=audience.rejected_candidate_ids,
                rationale=audience.rationale,
            ),
        ),
    )
    with pytest.raises(ValueError, match="must not overlap"):
        validate_annotation(bad_overlap)


def test_annotation_fingerprint_is_stable_and_covers_hidden_review_data():
    annotation = _annotation("gold-gift")
    first = annotation_fingerprint(annotation)
    second = annotation_fingerprint(annotation)
    changed = annotation_fingerprint(replace(annotation, unknowns=(*annotation.unknowns, "新增未知")))
    assert len(first) == 64
    assert first == second
    assert changed != first
