from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from mcn_incubation.evaluation import load_eval_cases
from mcn_incubation.preflight import (
    DuplicatePreflightRecord,
    IncompletePreflightRun,
    PreflightLedger,
    PreflightTamperDetected,
    build_preflight_prompt,
)

NOW = datetime(2026, 8, 10, 14, 0, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[3]
CASE_PATH = REPO_ROOT / "docs" / "mcn-incubation-v5" / "evidence" / "incubation-eval-cases.jsonl"


def test_preflight_prompt_uses_case_facts_without_leaking_the_mutation() -> None:
    case = load_eval_cases(CASE_PATH)[0]

    initial = build_preflight_prompt(case, include_mutation=False)
    mutated = build_preflight_prompt(case, include_mutation=True)

    assert case.scenario in initial
    assert all(fact in initial for fact in case.facts)
    assert case.mutation not in initial
    assert "不要联网补造" in initial
    assert "不得为主体新增身份、经历、客户案例或产品效果" in initial
    assert "价格、预算、频率和指标阈值" in initial
    assert "待验证变量" in initial
    assert "仅标成待验证并不能让任意数字变得有依据" in initial
    assert case.mutation in mutated
    assert "新补充证据" in mutated


def test_preflight_ledger_is_append_only_complete_and_tamper_evident(tmp_path: Path) -> None:
    ledger = PreflightLedger(tmp_path)
    manifest = ledger.create_run(
        run_id="run-001",
        model_id="pinned-model",
        trial_ids=("M01:initial", "B01:initial"),
        system_prompt_sha256="a" * 64,
        corpus_sha256="b" * 64,
        created_at=NOW,
    )
    prompt = "宝妈有十年会计经验，不展示孩子，应该怎么起号？"
    output = "先以小生意财务问题为核心，用桌面账本演示。"

    record = ledger.record_success(
        run_id=manifest.run_id,
        trial_id="M01:initial",
        prompt=prompt,
        output=output,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=3),
        usage={"input_tokens": 120, "output_tokens": 80},
    )

    assert record.input_sha256 == sha256(prompt.encode()).hexdigest()
    assert record.output_sha256 == sha256(output.encode()).hexdigest()
    assert ledger.verify_run("run-001").record_count == 1
    with pytest.raises(DuplicatePreflightRecord):
        ledger.record_success(
            run_id="run-001",
            trial_id="M01:initial",
            prompt=prompt,
            output=output,
            started_at=NOW,
            completed_at=NOW,
        )
    with pytest.raises(IncompletePreflightRun):
        ledger.complete_run("run-001", completed_at=NOW)

    ledger.record_failure(
        run_id="run-001",
        trial_id="B01:initial",
        prompt="品牌孵化预检",
        error_code="provider_timeout",
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=5),
    )
    completion = ledger.complete_run("run-001", completed_at=NOW + timedelta(seconds=6))

    assert completion.status == "completed_with_failures"
    assert completion.succeeded == 1
    assert completion.failed == 1
    assert ledger.verify_run("run-001").record_count == 2

    output_path = tmp_path / "run-001" / "outputs" / "M01_initial.md"
    output_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(PreflightTamperDetected):
        ledger.verify_run("run-001")
