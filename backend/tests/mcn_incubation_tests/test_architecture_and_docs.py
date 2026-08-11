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


def test_a20_to_a48_are_reviewed_and_source_backed() -> None:
    audit_paths = sorted(AUDIT_ROOT.glob("A*.md"))

    assert [path.name[:3] for path in audit_paths] == [f"A{index:02d}" for index in range(20, 49)]
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


def test_cross_domain_marketing_brain_uses_composable_lenses_not_industry_templates() -> None:
    audit = (AUDIT_ROOT / "A41-cross-domain-marketing-brain-architecture.md").read_text(encoding="utf-8")
    decision = (DOC_ROOT / "decisions" / "ADR-010-cross-domain-marketing-brain.md").read_text(encoding="utf-8")
    corpus_path = DOC_ROOT / "evidence" / "marketing-territory-contrast-cases.jsonl"
    cases = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    for discipline in ("营销科学", "消费者行为", "认知语义学", "人类学", "设计方法", "Agent 工程"):
        assert discipline in audit
    for contract_term in (
        "TerritoryCandidate",
        "IncubationDecisionVersion",
        "semantic_bridge",
        "recurring_situations",
        "attribution_path",
    ):
        assert contract_term in audit
    assert "if industry ==" in audit
    assert "不新增运行时" in decision
    assert "status: proposed" in decision
    assert "唯一 Lead Agent" in decision

    assert len(cases) == 6
    assert len({case["case_id"] for case in cases}) == len(cases)
    groups: dict[str, list[dict]] = {}
    for case in cases:
        groups.setdefault(case["contrast_group"], []).append(case)
        assert case["review_status"] == "needs_expert_review"
        assert case["subject_lenses"]
        assert case["known_facts"]
        assert case["business_goal"]
        assert case["must_change"]
        assert case["mutation"]

    assert set(groups) == {"fruit-business", "fruit-grower", "mother-role"}
    assert all(len(group_cases) == 2 for group_cases in groups.values())
    for group_cases in groups.values():
        assert len({case["surface_label"] for case in group_cases}) == 1
        assert len({tuple(case["known_facts"]) for case in group_cases}) == 2
        assert len({tuple(case["subject_lenses"]) for case in group_cases}) == 2


def test_marketing_territory_bakeoff_records_rejections_without_promoting_eval_context() -> None:
    audit = (AUDIT_ROOT / "A42-marketing-territory-bakeoff.md").read_text(encoding="utf-8")
    evidence = (DOC_ROOT / "evidence" / "2026-08-11-marketing-territory-bakeoff.md").read_text(encoding="utf-8")
    decision = (DOC_ROOT / "decisions" / "ADR-010-cross-domain-marketing-brain.md").read_text(encoding="utf-8")

    for marker in ("24", "26", "61,361", "TerritoryCandidate", "两遍法", "部分命中"):
        assert marker in audit
    assert "没有候选通过" in audit
    assert "不接生产" in audit
    assert "结构化 JSON" in audit
    assert "territory-gold-anchor-two-pass-v2-20260811" in evidence
    assert "source-backed mechanism" in evidence
    assert "status: proposed" in decision


def test_content_world_reasoning_preserves_corrections_and_stays_out_of_production() -> None:
    audit = (AUDIT_ROOT / "A43-content-world-reasoning-and-charlie-course.md").read_text(encoding="utf-8")
    evidence = (DOC_ROOT / "evidence" / "2026-08-11-content-world-expert-corrections.md").read_text(encoding="utf-8")
    decision = (DOC_ROOT / "decisions" / "ADR-011-content-world-exploration.md").read_text(encoding="utf-8")
    product_contract = (DOC_ROOT / "current" / "PRODUCT_CONTRACT.md").read_text(encoding="utf-8")

    assert "019ff0ac-ebbf-7520-bae5-2b91f1c4da57" in evidence
    assert "不是业务成功案例" in evidence
    for marker in (
        "向上抽象",
        "向下拆分",
        "横向展开",
        "跨维连接",
        "时间 × 空间 × 事件 × 人物 × 冲突",
        "水果 -> 礼品",
        "榴莲",
    ):
        assert marker in evidence

    assert "27e48e10" in audit
    assert "查理" in audit
    assert "未找到可靠原始来源" in audit
    assert "课程来源" in audit
    assert "第五版综合" in audit
    assert "不使用关键词决定" in audit
    assert "不引入向量数据库" in audit
    assert "参数知识" in audit
    assert "外部证据" in audit

    assert "status: proposed" in decision
    assert "可选认知算子" in decision
    assert "不是固定四步流程" in decision
    assert "叙事加工" in decision
    assert "营销取舍" in decision
    assert "内容世界探索" in product_contract

    production_files = (
        PACKAGE_ROOT / "agent_contract.py",
        PACKAGE_ROOT / "methods.py",
        PACKAGE_ROOT / "knowledge.py",
    )
    for path in production_files:
        text = path.read_text(encoding="utf-8")
        assert "content-world-exploration-v1" not in text
        assert "时间 × 空间 × 事件 × 人物 × 冲突" not in text


def test_conversation_operator_trial_records_business_rejection_without_production_promotion() -> None:
    audit = (AUDIT_ROOT / "A44-conversation-content-world-trial.md").read_text(encoding="utf-8")
    evidence = (DOC_ROOT / "evidence" / "2026-08-11-content-world-operator-trial.md").read_text(encoding="utf-8")
    decision = (DOC_ROOT / "decisions" / "ADR-011-content-world-exploration.md").read_text(encoding="utf-8")

    for marker in (
        "content-world-conversation-v1-20260811",
        "4/4",
        "10,278",
        "CW01-gold-gift",
        "CW02-fruit-world",
        "business-rejected",
    ):
        assert marker in audit
        assert marker in evidence
    assert "没有进入送、收、拒、回与人情世界" in audit
    assert "没有展开母世界、子世界、五维叙事或跨维连接" in audit
    assert "未使用查理" in audit
    assert "不接生产" in audit
    assert "单遍方法卡候选已被拒绝" in decision
    assert "status: proposed" in decision

    production_files = (
        PACKAGE_ROOT / "agent_contract.py",
        PACKAGE_ROOT / "methods.py",
        PACKAGE_ROOT / "knowledge.py",
    )
    for path in production_files:
        text = path.read_text(encoding="utf-8")
        assert "content_world_operators" not in text
        assert "CONTENT_WORLD_OPERATOR_CARD" not in text


def test_template_origin_audit_traces_the_exact_payload_and_keeps_the_repair_eval_only() -> None:
    audit = (AUDIT_ROOT / "A45-content-world-template-origin.md").read_text(encoding="utf-8")
    evidence = (DOC_ROOT / "evidence" / "2026-08-11-content-world-prompt-provenance.md").read_text(encoding="utf-8")

    for marker in (
        "messages_exact=True",
        "message_count=2",
        "has_tools=False",
        "has_previous_response_id=False",
        "PatchedChatDeepSeek",
        "MT01-gold-gift",
        "B/C",
        "INCUBATION_AGENT_CONTRACT",
        "NATURAL_RESPONSE_CONTRACT",
        "模型默认先验",
        "任务边界混杂",
        "未使用查理",
        "未新增付费调用",
    ):
        assert marker in audit
        assert marker in evidence

    assert "不是旧版记忆或 Skill 污染" in audit
    assert "不是完整 DeerFlow 母提示词注入" in audit
    assert "第五版共享孵化合同" in audit
    assert "不修改生产 Lead 提示词" in audit
    assert "content_world_exploration" in audit

    production_files = (
        PACKAGE_ROOT / "agent_contract.py",
        PACKAGE_ROOT / "methods.py",
        PACKAGE_ROOT / "knowledge.py",
        REPO_ROOT / "backend" / "packages" / "harness" / "deerflow" / "agents" / "lead_agent" / "prompt.py",
    )
    for path in production_files:
        text = path.read_text(encoding="utf-8")
        assert "CONTENT_WORLD_EXPLORATION_CONTEXT" not in text
        assert "CONTENT_WORLD_EXPLORATION_OPERATOR_CARD" not in text


def test_a46_wires_only_the_user_corrected_marketing_world_thinking_into_the_lead() -> None:
    audit = (AUDIT_ROOT / "A46-minimal-marketing-world-thinking-contract.md").read_text(encoding="utf-8")
    agent_contract = (PACKAGE_ROOT / "agent_contract.py").read_text(encoding="utf-8")

    for marker in (
        "019ff0ac-ebbf-7520-bae5-2b91f1c4da57",
        "MARKETING_WORLD_THINKING_CONTRACT",
        "定位",
        "内容",
        "表现形式",
        "用户真实情况暂不进入这个子任务",
        "未新增付费调用",
        "不宣称业务通过",
    ):
        assert marker in audit

    assert "MARKETING_WORLD_THINKING_CONTRACT" in agent_contract
    assert "内容来源不能冒充表现形式" in agent_contract
    assert "不是必须依次执行的流程" in agent_contract
    assert "CONTENT_WORLD_EXPLORATION_CONTEXT" not in agent_contract
    assert "CONTENT_WORLD_EXPLORATION_OPERATOR_CARD" not in agent_contract


def test_a47_records_the_real_production_lead_trial_as_business_rejected() -> None:
    audit = (AUDIT_ROOT / "A47-production-lead-content-world-trial.md").read_text(encoding="utf-8")
    evidence = (DOC_ROOT / "evidence" / "2026-08-11-production-lead-content-world-trial.md").read_text(encoding="utf-8")

    for marker in (
        "agent-eval-content-world-production-v1-20260811",
        "0 events",
        "0 Token",
        "agent-eval-content-world-production-v2-20260811",
        "2/2",
        "64,005",
        "business-rejected",
        "af0a38290e219b6c6bb6c89d9d8453f737b7c5957fb8d84cfaf8b5baaf69b942",
        "a496f1a4f0a38ea652fdecd27f977ff236feea215cc7f15a3b4ff5153083541c",
        "content-engine-v1",
        "incubation-model-v1",
        "黄金仍是语义中心",
        "三年以上",
        "未新增第二轮付费复测",
    ):
        assert marker in audit
        assert marker in evidence

    assert "方法检索重新引入完整孵化压力" in audit
    assert "待验证推断" in audit
    assert "水果存在局部进步" in evidence


def test_a48_records_method_context_as_a_material_but_not_sole_failure_contributor() -> None:
    audit = (AUDIT_ROOT / "A48-method-context-ablation.md").read_text(encoding="utf-8")
    evidence = (DOC_ROOT / "evidence" / "2026-08-11-method-context-ablation.md").read_text(encoding="utf-8")

    for marker in (
        "agent-eval-content-world-production-v2-20260811",
        "agent-eval-content-world-no-method-v1-20260811",
        "method_context_mode",
        "disabled",
        "59,967",
        "4,038",
        "d46d944c6c15305ae07cce13b2259002ab05849b0f54bcad8a2606e13569a043",
        "27fcdbccf06b2127f7c3bc0ded04270494c105859ee08a17a035067eab9cfed1",
        "黄金只是载体",
        "杨贵妃",
        "糖尿病",
        "business-rejected",
        "重要干扰源",
        "不是唯一病根",
        "不从生产环境全局删除方法系统",
    ):
        assert marker in audit
        assert marker in evidence

    assert "8261b541b737422f147d90f68515a6ed8bcffb0bc90606c2c49dfc88c974a9c8" in evidence
    assert "9db90f6541045b97714451afdcbc32513380484b32e22b364a058e5460ea82a8" in evidence
