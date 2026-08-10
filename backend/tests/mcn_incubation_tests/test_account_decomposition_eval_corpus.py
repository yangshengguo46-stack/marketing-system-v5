from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "account-decomposition-eval-cases.jsonl"


def _load_cases() -> list[dict]:
    return [json.loads(line) for line in EVAL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_account_decomposition_eval_corpus_covers_platforms_and_evidence_failures() -> None:
    cases = _load_cases()

    assert len(cases) >= 10
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {case["platform"] for case in cases} == {
        "bilibili",
        "douyin",
        "kuaishou",
        "tiktok",
        "wechat_channels",
        "xiaohongshu",
    }

    covered_risks = {risk for case in cases for risk in case["risks"]}
    assert {
        "account_identity_ambiguity",
        "cross_platform_identity_confusion",
        "media_rights_or_cloud_consent",
        "metric_capture_time_mismatch",
        "missing_public_metrics",
        "modality_conflict",
        "one_hit_outlier",
        "private_or_login_expired",
        "small_sample",
        "strategy_copying",
        "time_period_drift",
    }.issubset(covered_risks)


def test_account_decomposition_cases_require_traceable_observations_not_causal_templates() -> None:
    required_capabilities = {
        "canonical_identity",
        "counterexamples",
        "coverage_disclosure",
        "media_atoms",
        "pattern_hypotheses",
        "rights_and_privacy",
        "transparent_sampling",
    }

    cases = _load_cases()
    covered_capabilities = {capability for case in cases for capability in case["expected_capabilities"]}
    assert required_capabilities.issubset(covered_capabilities)

    for case in cases:
        assert case["scenario"]
        assert case["expected_capabilities"]
        assert case["forbidden_conclusions"]
        assert "universal_success_formula" in case["forbidden_conclusions"]
        assert "causal_performance_claim" in case["forbidden_conclusions"]
