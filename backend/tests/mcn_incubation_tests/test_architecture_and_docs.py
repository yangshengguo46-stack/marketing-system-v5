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


def test_a20_to_a30_are_reviewed_and_source_backed() -> None:
    audit_paths = sorted(AUDIT_ROOT.glob("A*.md"))

    assert [path.name[:3] for path in audit_paths] == [f"A{index:02d}" for index in range(20, 31)]
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
