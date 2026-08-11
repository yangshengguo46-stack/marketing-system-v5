from __future__ import annotations

from deerflow.tools.builtins.incubation_context_tool import incubation_context_tool
from deerflow.tools.tools import BUILTIN_TOOLS

M01_TRACE_QUERY = "十年会计经验宝妈，不展示孩子，每周8小时，验证小生意财务咨询需求，起号策略内容形式变现闭环最小实验"
XHS_MCN_SOURCE_ID = "url:https://creator.xiaohongshu.com/mcn-introduce?source=agora"


def test_incubation_context_is_one_advisory_builtin_not_an_agent_or_workflow() -> None:
    result = incubation_context_tool.invoke(
        {
            "query": "做过十年会计的宝妈不展示孩子，怎么选择表现形式和变现路径",
            "limit": 4,
        }
    )

    assert incubation_context_tool in BUILTIN_TOOLS
    assert result["authority"] == "advisory_context_only"
    assert 1 <= len(result["methods"]) <= 4
    assert {"expression_form", "monetization"}.issubset({method["capability"] for method in result["methods"]})
    assert all(method["source_refs"] for method in result["methods"])
    assert {ref for method in result["methods"] for ref in method["source_refs"]} == {source["source_id"] for source in result["sources"]}
    assert all(source["kind"] for source in result["sources"])
    assert all(source["supported_claims"] for source in result["sources"])
    assert all(source["limitations"] for source in result["sources"])
    assert "workflow" not in result
    assert "next_stage" not in result


def test_incubation_context_returns_no_fake_match_instead_of_dumping_every_method() -> None:
    result = incubation_context_tool.invoke({"query": "量子纠缠公式推导", "limit": 4})

    assert result["methods"] == []
    assert "No reviewed method card matched" in result["note"]


def test_incubation_context_keeps_platform_scope_and_source_limits_visible() -> None:
    result = incubation_context_tool.invoke(
        {
            "query": "拆解 TikTok 对标账号，产品实测怎样形成可信证明但不能照抄",
            "limit": 5,
        }
    )

    capabilities = {method["capability"] for method in result["methods"]}
    assert {"trust_proof", "benchmark_adaptation"}.issubset(capabilities)
    tiktok_sources = [source for source in result["sources"] if source["applicable_platforms"] == ["tiktok"]]
    assert len(tiktok_sources) == 1
    assert "TikTok One" in " ".join(tiktok_sources[0]["limitations"])


def test_m01_trace_query_recovers_material_lenses_without_platform_anchoring() -> None:
    result = incubation_context_tool.invoke({"query": M01_TRACE_QUERY})

    capabilities = {method["capability"] for method in result["methods"]}
    assert {
        "positioning",
        "expression_form",
        "content_engine",
        "monetization",
        "conversion",
        "experiment_design",
    }.issubset(capabilities)
    assert XHS_MCN_SOURCE_ID not in {source["source_id"] for source in result["sources"]}
