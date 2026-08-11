from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from mcn_incubation.domain import IncubationProject, SubjectKind, TruthKind
from mcn_incubation.persistence import IncubationRepository, OwnershipViolation
from mcn_incubation.persistence_schema import bootstrap_incubation_schema
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from deerflow.tools.builtins.incubation_subject_answer_tool import (
    incubation_record_subject_answer_tool,
)
from deerflow.tools.tools import BUILTIN_TOOLS

NOW = datetime(2026, 8, 11, 15, 0, tzinfo=UTC)
ANSWER_MODULE = importlib.import_module("deerflow.tools.builtins.incubation_subject_answer_tool")


def _request(
    request_id: str,
    question: str,
    *,
    clarification_type: str = "missing_info",
) -> ToolMessage:
    return ToolMessage(
        id=request_id,
        name="ask_clarification",
        tool_call_id=request_id.removeprefix("clarification:"),
        content=question,
        artifact={
            "human_input": {
                "version": 1,
                "kind": "human_input_request",
                "source": "ask_clarification",
                "request_id": request_id,
                "clarification_type": clarification_type,
                "question": question,
                "input_mode": "free_text",
            }
        },
    )


def _response(request_id: str, value: str, *, run_id: str) -> HumanMessage:
    return HumanMessage(
        content=value,
        additional_kwargs={
            "run_id": run_id,
            "hide_from_ui": True,
            "human_input_response": {
                "version": 1,
                "kind": "human_input_response",
                "source": "ask_clarification",
                "request_id": request_id,
                "response_kind": "text",
                "value": value,
            },
        },
    )


def _runtime(
    user_id: str,
    messages: list,
    *,
    run_id: str = "run-current",
    thread_id: str = "thread-a",
    is_subagent: bool = False,
) -> ToolRuntime:
    context = {"user_id": user_id, "thread_id": thread_id, "run_id": run_id}
    if is_subagent:
        context["is_subagent"] = True
    return ToolRuntime(
        state={"messages": messages, "sandbox": {}, "thread_data": {}},
        context=context,
        config={"configurable": {"thread_id": thread_id}},
        stream_writer=lambda _: None,
        tools=[],
        tool_call_id="capture-call",
        store=None,
    )


async def _project_repository(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'incubation.db'}")
    await bootstrap_incubation_schema(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = IncubationRepository(session_factory)
    await repository.create_project(
        IncubationProject(
            project_id="project-a",
            owner_id="owner-a",
            working_title="会计宝妈起号",
            subject_kind=SubjectKind.PERSON,
            created_at=NOW,
        ),
        operation_key="create-project",
    )
    return engine, session_factory, repository


@pytest.mark.asyncio
async def test_subject_answer_records_exact_current_human_reply_as_user_fact(
    monkeypatch,
    tmp_path,
) -> None:
    engine, session_factory, repository = await _project_repository(tmp_path)
    request_id = "clarification:camera-fit"
    question = "你实际面对镜头时，更接近自然表达、紧张但可练，还是完全不愿露脸？"
    answer = "面对镜头会紧张，但我愿意先拍手部和桌面。"
    try:
        monkeypatch.setattr(ANSWER_MODULE, "get_session_factory", lambda: session_factory)
        monkeypatch.setattr(ANSWER_MODULE, "_now_utc", lambda: NOW)

        result = await incubation_record_subject_answer_tool.coroutine(
            _runtime("owner-a", [_request(request_id, question), _response(request_id, answer, run_id="run-current")]),
            "project-a",
            "expression.camera_comfort",
        )

        truths = await repository.list_current_truths(owner_id="owner-a", project_id="project-a")
        assert result["status"] == "recorded"
        assert result["fact_key"] == "expression.camera_comfort"
        assert result["truth"]["kind"] == "user_fact"
        assert result["truth"]["statement"] == f"用户对问题“{question}”的回答：{answer}"
        assert result["truth"]["source_ref"].startswith("human-input://expression.camera_comfort/")
        assert "owner-a" not in repr(result)
        assert len(truths) == 1
        assert truths[0].kind is TruthKind.USER_FACT
        assert truths[0].statement == result["truth"]["statement"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_subject_answer_versions_one_fact_key_and_is_idempotent(
    monkeypatch,
    tmp_path,
) -> None:
    engine, session_factory, repository = await _project_repository(tmp_path)
    first_id = "clarification:camera-fit-v1"
    second_id = "clarification:camera-fit-v2"
    try:
        monkeypatch.setattr(ANSWER_MODULE, "get_session_factory", lambda: session_factory)
        monkeypatch.setattr(ANSWER_MODULE, "_now_utc", lambda: NOW)

        first = await incubation_record_subject_answer_tool.coroutine(
            _runtime("owner-a", [_request(first_id, "愿意露脸吗？"), _response(first_id, "不确定。", run_id="run-current")]),
            "project-a",
            "expression.camera_comfort",
        )
        duplicate = await incubation_record_subject_answer_tool.coroutine(
            _runtime("owner-a", [_request(first_id, "愿意露脸吗？"), _response(first_id, "不确定。", run_id="run-current")]),
            "project-a",
            "expression.camera_comfort",
        )
        same_request_other_thread = await incubation_record_subject_answer_tool.coroutine(
            _runtime(
                "owner-a",
                [_request(first_id, "愿意露脸吗？"), _response(first_id, "试拍后仍然不自然。", run_id="run-current")],
                thread_id="thread-b",
            ),
            "project-a",
            "expression.camera_comfort",
        )
        second = await incubation_record_subject_answer_tool.coroutine(
            _runtime(
                "owner-a",
                [_request(second_id, "试拍以后愿意采用哪种方式？"), _response(second_id, "只拍手部和桌面。", run_id="run-current")],
            ),
            "project-a",
            "expression.camera_comfort",
        )

        truths = await repository.list_current_truths(owner_id="owner-a", project_id="project-a")
        assert duplicate["status"] == "unchanged"
        assert duplicate["truth"]["truth_id"] == first["truth"]["truth_id"]
        assert same_request_other_thread["status"] == "recorded"
        assert same_request_other_thread["truth"]["supersedes_truth_id"] == first["truth"]["truth_id"]
        assert second["truth"]["supersedes_truth_id"] == same_request_other_thread["truth"]["truth_id"]
        assert [truth.truth_id for truth in truths] == [second["truth"]["truth_id"]]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_subject_answer_rejects_stale_unmatched_and_approval_responses(
    monkeypatch,
    tmp_path,
) -> None:
    engine, session_factory, _repository = await _project_repository(tmp_path)
    request_id = "clarification:camera-fit"
    try:
        monkeypatch.setattr(ANSWER_MODULE, "get_session_factory", lambda: session_factory)

        with pytest.raises(ValueError, match="current run"):
            await incubation_record_subject_answer_tool.coroutine(
                _runtime("owner-a", [_request(request_id, "愿意露脸吗？"), _response(request_id, "不愿意。", run_id="run-old")]),
                "project-a",
                "expression.camera_comfort",
            )
        with pytest.raises(ValueError, match="matching clarification request"):
            await incubation_record_subject_answer_tool.coroutine(
                _runtime("owner-a", [_response(request_id, "不愿意。", run_id="run-current")]),
                "project-a",
                "expression.camera_comfort",
            )
        with pytest.raises(ValueError, match="approval"):
            await incubation_record_subject_answer_tool.coroutine(
                _runtime(
                    "owner-a",
                    [
                        _request(request_id, "确认发布吗？", clarification_type="risk_confirmation"),
                        _response(request_id, "确认。", run_id="run-current"),
                    ],
                ),
                "project-a",
                "expression.camera_comfort",
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_subject_answer_enforces_owner_and_durable_storage(
    monkeypatch,
    tmp_path,
) -> None:
    engine, session_factory, _repository = await _project_repository(tmp_path)
    request_id = "clarification:camera-fit"
    messages = [_request(request_id, "愿意露脸吗？"), _response(request_id, "不愿意。", run_id="run-current")]
    try:
        monkeypatch.setattr(ANSWER_MODULE, "get_session_factory", lambda: session_factory)
        with pytest.raises(OwnershipViolation):
            await incubation_record_subject_answer_tool.coroutine(
                _runtime("owner-b", messages),
                "project-a",
                "expression.camera_comfort",
            )

        monkeypatch.setattr(ANSWER_MODULE, "get_session_factory", lambda: None)
        unavailable = await incubation_record_subject_answer_tool.coroutine(
            _runtime("owner-a", messages),
            "project-a",
            "expression.camera_comfort",
        )
        assert unavailable == {
            "authority": "project_truth_ledger",
            "project_id": "project-a",
            "status": "unavailable",
            "note": "Durable project truth is unavailable; the answer was not recorded and must not be replaced with chat memory or a model summary.",
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_subject_answer_is_lead_only_even_if_a_subagent_receives_the_tool(
    monkeypatch,
    tmp_path,
) -> None:
    engine, session_factory, _repository = await _project_repository(tmp_path)
    request_id = "clarification:camera-fit"
    try:
        monkeypatch.setattr(ANSWER_MODULE, "get_session_factory", lambda: session_factory)
        with pytest.raises(PermissionError, match="Lead Agent"):
            await incubation_record_subject_answer_tool.coroutine(
                _runtime(
                    "owner-a",
                    [_request(request_id, "愿意露脸吗？"), _response(request_id, "不愿意。", run_id="run-current")],
                    is_subagent=True,
                ),
                "project-a",
                "expression.camera_comfort",
            )
    finally:
        await engine.dispose()


def test_subject_answer_tool_schema_cannot_accept_owner_or_answer_text() -> None:
    parameters = convert_to_openai_tool(incubation_record_subject_answer_tool)["function"]["parameters"]

    assert incubation_record_subject_answer_tool in BUILTIN_TOOLS
    assert set(parameters["properties"]) == {"project_id", "fact_key"}
    assert "owner_id" not in parameters["properties"]
    assert "answer" not in parameters["properties"]
    assert "question" not in parameters["properties"]
