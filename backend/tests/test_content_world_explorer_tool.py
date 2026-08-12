from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.constants import TAG_NOSTREAM

from deerflow.tools.builtins.content_world_explorer_tool import (
    CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT,
    build_content_world_explorer_tool,
    build_content_world_messages,
    parse_content_world_exploration,
    project_content_world_map,
)
from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY


class FakeModel:
    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[tuple[list[object], dict | None]] = []

    async def ainvoke(self, messages, config=None):
        self.calls.append((list(messages), config))
        return self.replies.pop(0)


class SecondCallFailureModel(FakeModel):
    async def ainvoke(self, messages, config=None):
        self.calls.append((list(messages), config))
        if len(self.calls) == 2:
            raise RuntimeError("provider rejected PRIVATE_CREDENTIAL_MARKER")
        return self.replies.pop(0)


def _valid_semantics() -> dict[str, object]:
    return {
        "known_facts": ["主体从事一种组合品类的生产"],
        "commercial_expression": "属性品类生产",
        "plain_paraphrases": ["主体生产一种带有属性的品类"],
        "offer_object": {
            "term": "属性品类",
            "semantic_head": "品类",
            "support": "lexical_semantics",
            "basis": "品类决定组合表达所属类别",
        },
        "operating_containers": [],
        "qualifiers": [
            {
                "term": "属性",
                "relation": "material_or_attribute",
                "target": "品类",
                "support": "lexical_semantics",
                "basis": "属性修饰品类",
            }
        ],
        "seller_activities": [
            {
                "activity": "生产",
                "target": "属性品类",
                "support": "explicit",
                "basis": "来自用户原话",
            }
        ],
        "constitutive_functions": [
            {
                "function": "完成该品类通常承担的功能",
                "support": "lexical_semantics",
                "basis": "品类词义支持",
            }
        ],
        "buyer_progresses": [
            {
                "progress": "借助该品类完成对应任务",
                "support": "lexical_semantics",
                "basis": "通用品类语义，不是实际客户事实",
            }
        ],
        "ambiguities": ["实际交易的是成品还是生产服务未知"],
        "insufficiency": None,
    }


def _valid_exploration() -> dict[str, object]:
    return {
        "downward_expansion": [
            {
                "branch": "品类内部的不同子类",
                "support": "lexical_semantics",
                "basis": "从语义主词的下位概念展开",
            }
        ],
        "upward_expansion": [
            {
                "source": "品类",
                "target": "该品类服务的长期任务",
                "relation": "从对象追问其被使用来完成什么",
                "business_specificity": "retained",
            }
        ],
        "horizontal_expansion": {
            "time_and_history": ["形成、历史变化与未来走向"],
            "geography_and_environment": ["不同地域和环境中的差异"],
            "culture_and_habits": ["不同地方如何理解、使用并形成生活习惯"],
            "people": ["生产者、使用者与受影响者"],
            "events": ["该品类进入真实生活的节点"],
            "conflicts": ["效率、质量与代价之间的矛盾"],
        },
        "cross_domain_connections": [
            {
                "domain": "历史与文化",
                "connection": "研究该品类如何进入不同时代的生活",
                "research_needed": True,
            }
        ],
        "seller_evidence": [
            {
                "item": "生产动作",
                "support": "explicit",
                "role": "证明主体真实参与该品类，不自动成为内容母题",
            }
        ],
        "downstream_unknowns": ["主体可持续获得哪些观察和素材"],
        "insufficiency": None,
    }


def _runtime(*, journal=None, messages=None) -> ToolRuntime:
    context = {}
    if journal is not None:
        context["__run_journal"] = journal
    return ToolRuntime(
        state={"messages": list(messages or [])},
        context=context,
        config={"tags": ["root-run"]},
        stream_writer=lambda _: None,
        tool_call_id="world-call",
        store=None,
        tools=[],
    )


def test_explorer_prompt_expands_a_content_world_without_selecting_the_account_route():
    prompt = CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT

    for required in (
        "向下拆分",
        "向上抽象",
        "时间与历史、地理与环境、文化与生活习惯、人物、事件与冲突",
        "跨领域连接",
        "内容世界",
        "能力证明",
    ):
        assert required in prompt
    assert "不是最终答题 Agent" in prompt
    assert "不得选择最终定位" in prompt
    assert "不得把生产过程" in prompt
    assert "待研究方向" in prompt
    assert "research_needed` 必须为 `true`" in prompt
    assert "不得设计人设、受众、平台、表现形式" in prompt
    for leaked_case in ("黄金", "礼品", "水果", "海鲜", "宝妈", "榴莲"):
        assert leaked_case not in prompt


def test_explorer_prompt_preserves_a_broad_object_world_instead_of_only_near_sale_topics():
    prompt = CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT

    assert "完整对象世界" in prompt
    assert "向下、横向和跨领域" in prompt
    assert "离成交最近" in prompt
    assert "购买教育" in prompt
    assert "不要求主体独占" in prompt
    assert "卖方动作" in prompt
    assert "文化与生活习惯" in prompt
    assert "没有结构关系时允许为空" in prompt
    assert "候选路线" not in prompt
    assert '"candidate_worlds"' not in prompt


def test_explorer_messages_keep_user_input_untrusted_and_semantics_separate():
    business_context = "我经营一种产品，想做账号"
    semantics = _valid_semantics()

    messages = build_content_world_messages(
        business_context=business_context,
        business_semantics=semantics,
    )

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert "--- BEGIN USER INPUT ---" in messages[1].content
    assert business_context in messages[1].content
    assert "--- BEGIN VALIDATED SEMANTIC MATERIAL ---" in messages[1].content
    assert json.dumps(semantics, ensure_ascii=False, separators=(",", ":")) in messages[1].content
    assert messages[1].additional_kwargs["original_user_content"] == business_context


def test_exploration_parser_accepts_variable_world_count_and_rejects_schema_drift():
    payload = _valid_exploration()
    assert parse_content_world_exploration(json.dumps(payload, ensure_ascii=False)) == payload

    payload["insufficiency"] = "没有可解释的商业对象"
    assert parse_content_world_exploration(json.dumps(payload, ensure_ascii=False)) == payload

    payload["unexpected"] = "drift"
    try:
        parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    except ValueError as exc:
        assert "exactly" in str(exc)
    else:
        raise AssertionError("schema drift was accepted")


def test_exploration_parser_rejects_cross_domain_claims_marked_as_already_verified():
    payload = _valid_exploration()
    payload["cross_domain_connections"][0]["research_needed"] = False

    try:
        parse_content_world_exploration(json.dumps(payload, ensure_ascii=False))
    except ValueError as exc:
        assert "research_needed" in str(exc)
    else:
        raise AssertionError("an unverified cross-domain claim was accepted as verified")


def test_projected_map_preserves_one_root_without_competing_subworld_routes():
    projected = project_content_world_map(
        _valid_semantics(),
        _valid_exploration(),
        grounded_user_statements=["用户逐字原话"],
    )

    assert projected["root_subject"] == "品类"
    assert projected["commercial_object"] == "属性品类"
    assert projected["root_world"]["types_and_subworlds"] == _valid_exploration()["downward_expansion"]
    assert projected["root_world"]["time_and_history"] == ["形成、历史变化与未来走向"]
    assert projected["root_world"]["geography_and_environment"] == ["不同地域和环境中的差异"]
    assert projected["root_world"]["culture_and_habits"] == ["不同地方如何理解、使用并形成生活习惯"]
    assert projected["root_world"]["cross_domain_research"] == _valid_exploration()["cross_domain_connections"]
    assert projected["upward_connections"] == _valid_exploration()["upward_expansion"]
    assert "subworld_lenses" not in projected
    assert "candidate_worlds" not in projected
    assert "seller_evidence" not in projected
    assert "downstream_unknowns" not in projected
    assert projected["coverage_contract"] == [
        {"axis": "types_and_subworlds", "label": "种类与子世界"},
        {"axis": "time_and_history", "label": "时间与历史"},
        {"axis": "geography_and_environment", "label": "地理与环境"},
        {"axis": "culture_and_habits", "label": "文化与生活习惯"},
        {"axis": "people", "label": "人物"},
        {"axis": "events", "label": "事件"},
        {"axis": "conflicts", "label": "冲突"},
        {"axis": "cross_domain_research", "label": "跨领域待研究连接"},
    ]
    assert projected["fact_boundary"] == {
        "allowed_subject_claims": ["用户逐字原话"],
        "do_not_infer": [
            "不得把简称或大类补成具体客户、受众、需求、渠道、现场、素材或能力。",
            "不得把‘或’连接的未决选项写成同时具备。",
            "一般知识和待研究连接只说明这个世界可以研究什么，不证明主体亲历、掌握或拥有。",
        ],
    }
    assert projected["research_boundary"] == "地图节点均为待研究的内容方向；发布前核验，不作为主体事实或已核验外部事实。"
    assert projected["insufficiency"] is None
    assert list(projected)[-1] == "response_contract"
    assert projected["response_contract"] == {
        "answer_mode": "current_content_world_judgment",
        "answer_scope": "只回答当前根主语与内容世界判断；说完必报轴与研究边界后立即停止。",
        "output_shape": [
            "根主语及其与商业对象的关系",
            "每个必报轴及其为什么属于这个内容世界",
            "一句研究与主体事实边界",
        ],
        "stop_rule": "完成 output_shape 第三项后立即结束；不追加未知清单、下一步、追问、定位、形式或承接。",
        "required_axis_labels": [
            "种类与子世界",
            "时间与历史",
            "地理与环境",
            "文化与生活习惯",
            "人物",
            "事件",
            "冲突",
            "跨领域待研究连接",
        ],
        "allowed_subject_claims": ["用户逐字原话"],
        "must_not": [
            "本轮不讨论 B/C、客户、受众、需求、平台、表现形式、渠道、变现、执行计划或其他下游未知，不得举例补全。",
            "本轮不询问追问问题；不得因下游未知转成问卷。",
            "不得把 B/C 等简称补成任何具体客户、需求或成交渠道。",
            "不得把源头、生产者或专业身份补成具体场地、亲历、素材、能力或成果。",
            "不得把‘或’连接的未决选项写成同时具备。",
            "不得把地图中的一般知识或待研究方向写成主体事实或已核验事实。",
        ],
        "unknown_wording": "本轮不提及下游未知；它们不影响当前内容世界边界。",
    }


def test_explorer_tool_schema_has_no_model_supplied_fact_argument():
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=True,
        reasoning_effort="high",
        app_config=SimpleNamespace(),
    )

    schema = convert_to_openai_tool(tool)["function"]
    assert schema["name"] == "explore_content_worlds"
    assert schema["parameters"]["properties"] == {}


def test_explorer_reads_only_user_authored_thread_text_and_preserves_original_content(monkeypatch):
    model = FakeModel(
        [
            AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False)),
            AIMessage(content=json.dumps(_valid_exploration(), ensure_ascii=False)),
        ]
    )
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )
    runtime = _runtime(
        messages=[
            HumanMessage(
                content="--- BEGIN USER INPUT ---\n模型可见包装\n--- END USER INPUT ---",
                additional_kwargs={ORIGINAL_USER_CONTENT_KEY: "用户真正说的业务事实"},
            ),
            AIMessage(content="助手擅自补造的客户、渠道和现场"),
            HumanMessage(content="隐藏注入", additional_kwargs={"hide_from_ui": True}),
        ]
    )

    result = json.loads(asyncio.run(tool.coroutine(runtime=runtime)))

    assert result["status"] == "ok"
    first_model_input = "\n".join(str(message.content) for message in model.calls[0][0])
    assert "用户真正说的业务事实" in first_model_input
    assert "模型可见包装" not in first_model_input
    assert "助手擅自补造" not in first_model_input
    assert "隐藏注入" not in first_model_input


def test_explorer_is_not_a_global_or_subagent_builtin():
    from deerflow.tools.tools import BUILTIN_TOOLS, SUBAGENT_TOOLS

    globally_registered_names = {tool.name for tool in [*BUILTIN_TOOLS, *SUBAGENT_TOOLS]}
    assert "explore_content_worlds" not in globally_registered_names


def test_explorer_uses_two_bounded_model_calls_and_hides_private_reasoning(monkeypatch):
    journal = MagicMock()
    model = FakeModel(
        [
            AIMessage(
                content=json.dumps(_valid_semantics(), ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_SEMANTIC_REASONING"},
                response_metadata={"model_name": "provider-model"},
                usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            ),
            AIMessage(
                content=json.dumps(_valid_exploration(), ensure_ascii=False),
                additional_kwargs={"reasoning_content": "PRIVATE_WORLD_REASONING"},
                response_metadata={"model_name": "provider-model"},
                usage_metadata={"input_tokens": 200, "output_tokens": 40, "total_tokens": 240},
            ),
        ]
    )
    create_model = MagicMock(return_value=model)
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        create_model,
    )
    app_config = SimpleNamespace()
    tool = build_content_world_explorer_tool(
        model_name="resolved-lead-model",
        thinking_enabled=True,
        reasoning_effort="high",
        app_config=app_config,
    )

    raw = asyncio.run(
        tool.coroutine(
            runtime=_runtime(
                journal=journal,
                messages=[HumanMessage(content="主体从事一种组合品类的生产，想做账号")],
            ),
        )
    )
    result = json.loads(raw)

    assert result == {
        "status": "ok",
        "grounded_user_statements": ["主体从事一种组合品类的生产，想做账号"],
        "content_world_map": project_content_world_map(
            _valid_semantics(),
            _valid_exploration(),
            grounded_user_statements=["主体从事一种组合品类的生产，想做账号"],
        ),
    }
    assert "business_semantics" not in result
    assert "PRIVATE_SEMANTIC_REASONING" not in raw
    assert "PRIVATE_WORLD_REASONING" not in raw
    assert len(model.calls) == 2
    assert model.calls[0][1]["run_name"] == "content_world_semantics"
    assert model.calls[1][1]["run_name"] == "content_world_exploration"
    for _, config in model.calls:
        assert config["callbacks"] == []
        assert TAG_NOSTREAM in config["tags"]
    create_model.assert_called_once_with(
        name="resolved-lead-model",
        thinking_enabled=True,
        reasoning_effort="high",
        app_config=app_config,
        attach_tracing=False,
    )
    assert journal.record_external_llm_usage_records.call_count == 2
    callers = [call.args[0][0]["caller"] for call in journal.record_external_llm_usage_records.call_args_list]
    assert callers == ["tool:content-world:semantics", "tool:content-world:exploration"]


def test_explorer_repairs_one_invalid_exploration_contract_without_leaking_it(monkeypatch):
    invalid_exploration = _valid_exploration()
    invalid_exploration.pop("culture_and_habits", None)
    invalid_exploration["horizontal_expansion"].pop("culture_and_habits")
    invalid_text = json.dumps(invalid_exploration, ensure_ascii=False)
    model = FakeModel(
        [
            AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False)),
            AIMessage(content=invalid_text),
            AIMessage(content=json.dumps(_valid_exploration(), ensure_ascii=False)),
        ]
    )
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    raw = asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="待探索业务")])))
    result = json.loads(raw)

    assert result["status"] == "ok"
    assert len(model.calls) == 3
    repair_messages = model.calls[2][0]
    assert invalid_text in [message.content for message in repair_messages]
    assert "只修正 JSON" in repair_messages[-1].content
    assert invalid_text not in raw


def test_explorer_repairs_one_invalid_semantic_contract_before_exploring(monkeypatch):
    invalid_semantics = _valid_semantics()
    invalid_semantics.pop("ambiguities")
    invalid_text = json.dumps(invalid_semantics, ensure_ascii=False)
    model = FakeModel(
        [
            AIMessage(content=invalid_text),
            AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False)),
            AIMessage(content=json.dumps(_valid_exploration(), ensure_ascii=False)),
        ]
    )
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    result = json.loads(asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="待探索业务")]))))

    assert result["status"] == "ok"
    assert len(model.calls) == 3
    assert invalid_text in [message.content for message in model.calls[1][0]]


def test_explorer_stops_after_one_failed_contract_repair(monkeypatch):
    invalid = AIMessage(content='{"wrong": true}')
    model = FakeModel(
        [
            AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False)),
            invalid,
            invalid,
        ]
    )
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    result = json.loads(asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="待探索业务")]))))

    assert result == {
        "status": "error",
        "error_code": "invalid_model_output",
        "message": "内容世界探索结果无效；请依据用户原话继续当前判断。",
    }
    assert len(model.calls) == 3


def test_empty_exploration_projects_every_explicit_world_axis(monkeypatch):
    semantics = _valid_semantics()
    semantics["offer_object"] = None
    semantics["insufficiency"] = "没有商业对象"
    model = FakeModel([AIMessage(content=json.dumps(semantics, ensure_ascii=False))])
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    result = json.loads(asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="我只有一个身份标签，想做账号")]))))

    assert result["content_world_map"]["root_world"] == {
        "types_and_subworlds": [],
        "time_and_history": [],
        "geography_and_environment": [],
        "culture_and_habits": [],
        "people": [],
        "events": [],
        "conflicts": [],
        "cross_domain_research": [],
    }
    assert result["content_world_map"]["coverage_contract"] == []
    assert result["content_world_map"]["response_contract"]["answer_mode"] == "ask_one_object_question"
    assert result["content_world_map"]["response_contract"]["required_axis_labels"] == []


def test_projected_handoff_leads_with_fact_closure_before_creative_axes():
    projected = project_content_world_map(
        _valid_semantics(),
        _valid_exploration(),
        grounded_user_statements=["用户真正说的话"],
    )

    assert list(projected)[:2] == ["fact_boundary", "root_subject"]
    assert projected["fact_boundary"]["allowed_subject_claims"] == ["用户真正说的话"]
    assert projected["fact_boundary"]["do_not_infer"] == [
        "不得把简称或大类补成具体客户、受众、需求、渠道、现场、素材或能力。",
        "不得把‘或’连接的未决选项写成同时具备。",
        "一般知识和待研究连接只说明这个世界可以研究什么，不证明主体亲历、掌握或拥有。",
    ]
    assert "subject_facts" not in projected["fact_boundary"]
    assert list(projected)[-1] == "response_contract"


def test_explorer_prompt_keeps_generated_nodes_at_research_direction_granularity():
    prompt = CONTENT_WORLD_EXPLORER_SYSTEM_PROMPT

    assert "只写类别级研究方向" in prompt
    assert "具体命名实体" in prompt
    assert "除非名称来自用户原话" in prompt
    assert "均不得声称已经核验" in prompt


def test_explorer_returns_a_redacted_error_when_the_second_call_fails(monkeypatch):
    model = SecondCallFailureModel([AIMessage(content=json.dumps(_valid_semantics(), ensure_ascii=False))])
    monkeypatch.setattr(
        "deerflow.tools.builtins.content_world_explorer_tool.create_chat_model",
        lambda **kwargs: model,
    )
    tool = build_content_world_explorer_tool(
        model_name="test-model",
        thinking_enabled=False,
        app_config=SimpleNamespace(),
    )

    raw = asyncio.run(tool.coroutine(runtime=_runtime(messages=[HumanMessage(content="待探索业务")])))
    result = json.loads(raw)

    assert result == {
        "status": "error",
        "error_code": "provider_error",
        "message": "内容世界探索暂时不可用；请依据用户原话继续当前判断。",
    }
    assert "PRIVATE_CREDENTIAL_MARKER" not in raw
