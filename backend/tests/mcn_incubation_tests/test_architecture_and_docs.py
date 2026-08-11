from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_ROOT = REPO_ROOT / "docs" / "mcn-incubation-v5"
AUDIT_ROOT = DOC_ROOT / "audits"
PACKAGE_ROOT = REPO_ROOT / "backend" / "packages" / "mcn-incubation-core" / "mcn_incubation"


def test_a20_to_a40_are_reviewed_and_source_backed() -> None:
    audit_paths = sorted(AUDIT_ROOT.glob("A*.md"))

    assert [path.name[:3] for path in audit_paths] == [f"A{index:02d}" for index in range(20, 41)]
    for path in audit_paths:
        text = path.read_text(encoding="utf-8")
        assert re.search(r"^status: reviewed$", text, re.MULTILINE), path
        assert re.search(r"^sources:$", text, re.MULTILINE), path
        assert "## 结论" in text, path
        assert "## 第五版决定" in text, path


def test_v4_skill_reuse_matrix_is_complete_and_keeps_decision_authority_with_the_lead_agent() -> None:
    matrix_path = DOC_ROOT / "evidence" / "v4-skill-reuse-matrix.json"
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    entries = payload["skills"]
    by_name = {entry["name"]: entry for entry in entries}

    assert payload["schema_version"] == "mcn-incubation-v5-v4-skill-reuse-v1"
    assert payload["source"]["commit"] == "58f4e0c900a2dc589fe4a23bdebbe8e3211b67b7"
    assert payload["source"]["sorted_skill_name_inventory_sha256"] == "9cbc411230a4383fab5bacf95840e717ce13b982457360132b880584742fcff8"
    inventory = "".join(f"{name}\n" for name in sorted(by_name))
    assert hashlib.sha256(inventory.encode()).hexdigest() == payload["source"]["sorted_skill_name_inventory_sha256"]
    assert len(entries) == 97
    assert len(by_name) == 97
    assert {entry["decision"] for entry in entries} == {
        "already_present",
        "adopt_on_demand",
        "distill_method",
        "rewrite_adapter",
        "exclude",
    }

    assert by_name["personal-ip-operator"]["decision"] == "exclude"
    assert by_name["build-cinematic-ip-system"]["decision"] == "exclude"
    assert by_name["ip-strategy-director"]["decision"] == "distill_method"
    assert by_name["video-pattern-learning"]["decision"] == "adopt_on_demand"
    assert by_name["write-ip-episode"]["decision"] == "adopt_on_demand"
    assert by_name["product-ad-production"]["decision"] == "adopt_on_demand"
    assert by_name["diagnose-douyin-account"]["decision"] == "distill_method"
    assert by_name["byted-mediakit-video"]["decision"] == "already_present"

    for entry in entries:
        assert entry["role"] in {
            "existing_general_capability",
            "incubation_method",
            "evidence_interpretation",
            "content_craft",
            "media_execution",
            "platform_execution",
            "retired_or_out_of_scope",
        }
        assert entry["reason"].strip()


def test_new_core_is_independent_from_legacy_marketing_and_agent_runtimes() -> None:
    python_files = sorted(PACKAGE_ROOT.rglob("*.py"))

    assert python_files
    violations: list[str] = []
    for path in python_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name == "marketing_os" or name.startswith("marketing_os."):
                    violations.append(f"{path.name} imports legacy {name}")
                if name == "app" or name.startswith("app."):
                    violations.append(f"{path.name} imports host {name}")
                if name.startswith("deerflow.agents"):
                    violations.append(f"{path.name} imports agent runtime {name}")

    assert violations == []


def test_new_core_contains_no_semantic_middleware_or_out_of_scope_film_system() -> None:
    forbidden = {
        "AgentMiddleware": "semantic middleware",
        "SystemMessage": "prebuilt prompt message",
        "tool_choice": "forced tool route",
        "request.override": "model request rewrite",
        "cinematic": "out-of-scope film system",
        "电影化": "out-of-scope film system",
    }
    violations: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token, reason in forbidden.items():
            if token in text:
                violations.append(f"{path.name}: {reason} ({token})")

    assert violations == []


def test_architecture_decision_cannot_claim_a_winner_before_live_bakeoff() -> None:
    decision = (DOC_ROOT / "decisions" / "ADR-006-incubation-core-architecture.md").read_text(encoding="utf-8")
    ledger = (DOC_ROOT / "current" / "EXECUTION_LEDGER.md").read_text(encoding="utf-8")

    assert "status: proposed" in decision
    assert "尚未产生架构胜者" in decision
    assert "真实模型竞赛" in ledger
    assert "未完成" in ledger


def test_internal_codename_does_not_freeze_the_public_product_name() -> None:
    contract = (DOC_ROOT / "current" / "PRODUCT_CONTRACT.md").read_text(encoding="utf-8")

    assert "mcn-incubation-core" in contract
    assert "内部工作名" in contract
    assert "产品名称未定" in contract


def test_multiagent_decision_keeps_one_incubation_authority() -> None:
    decision = (DOC_ROOT / "decisions" / "ADR-009-single-authority-multi-agent-trial.md").read_text(encoding="utf-8")
    product_contract = (DOC_ROOT / "current" / "PRODUCT_CONTRACT.md").read_text(encoding="utf-8")

    assert "status: proposed" in decision
    assert "Lead Agent" in decision
    assert "agents-as-tools" in decision
    assert "handoff" in decision
    assert "不强制委派" in decision
    assert "只读" in decision
    assert "唯一孵化决策权" in product_contract
    assert "子 Agent" in product_contract


def test_subject_answers_are_versioned_facts_without_becoming_an_intake_gate() -> None:
    audit = (AUDIT_ROOT / "A38-subject-question-answer-provenance.md").read_text(encoding="utf-8")
    product_contract = (DOC_ROOT / "current" / "PRODUCT_CONTRACT.md").read_text(encoding="utf-8")

    assert "status: reviewed" in audit
    assert "incubation_record_subject_answer" in audit
    assert "ProjectTruth" in audit
    assert "当前 run" in audit
    assert "固定问卷" in audit
    assert "用户原文" in product_contract
    assert "版本链" in product_contract
    assert "审批" in product_contract


def test_sparse_query_audit_rejects_both_no_question_and_forced_interview_extremes() -> None:
    audit = (AUDIT_ROOT / "A39-v4-interview-overcorrection-and-sparse-query.md").read_text(encoding="utf-8")

    for evidence_ref in (
        "019fade9-756b-7371-a697-a275ac9d02d3",
        "5fbabe36",
        "fc61bde6",
        "1aa2242b",
        "84ccb4dd",
    ):
        assert evidence_ref in audit
    assert "不新增独立访谈 Agent" in audit
    assert "不使用关键词拦截" in audit
    assert "不强制 `tool_choice`" in audit
    assert "不把字段完整度作为继续条件" in audit
    assert "先冻结失败评测" in audit


def test_marketing_brain_audit_preserves_category_action_and_commercial_return_path() -> None:
    sparse_audit = (AUDIT_ROOT / "A39-v4-interview-overcorrection-and-sparse-query.md").read_text(encoding="utf-8")
    brain_audit = (AUDIT_ROOT / "A40-marketing-brain-and-content-territory.md").read_text(encoding="utf-8")
    product_contract = (DOC_ROOT / "current" / "PRODUCT_CONTRACT.md").read_text(encoding="utf-8")
    corpus_path = DOC_ROOT / "evidence" / "marketing-territory-eval-cases.jsonl"
    cases = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    gold = next(case for case in cases if case["case_id"] == "MT01-gold-gift")

    assert "次要失败" in sparse_audit
    assert "A40" in sparse_audit
    assert "具体商品" in brain_audit
    assert "品类行为" in brain_audit
    assert "最大可占领" in brain_audit
    assert "最大语义距离" in brain_audit
    assert "Lead Agent" in brain_audit
    assert "不修改核心提示词" in brain_audit
    assert "品类行为" in product_contract
    assert "内容领地" in product_contract

    assert len(cases) == 8
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {case["review_status"] for case in cases} == {"expert_anchor", "needs_expert_review"}
    assert sum(case["review_status"] == "expert_anchor" for case in cases) == 1
    assert {"person", "brand", "product", "service", "organization"}.issubset({case["subject_kind"] for case in cases})
    for case in cases:
        assert case["known_facts"]
        assert case["observable_success"]
        assert case["observable_failures"]
        assert case["mutation"]

    assert gold["review_status"] == "expert_anchor"
    assert gold["expert_anchor"]["head_category"] == "礼品"
    assert "黄金" in gold["expert_anchor"]["modifiers"]
    assert "送礼" in gold["expert_anchor"]["category_actions"]
    assert any("具体商品" in item for item in gold["observable_success"])
    assert any("送礼" in item and "消失" in item for item in gold["observable_failures"])
    assert any("归因" in item for item in gold["observable_success"])
