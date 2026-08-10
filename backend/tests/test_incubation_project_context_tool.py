from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from langchain.tools import ToolRuntime
from langchain_core.utils.function_calling import convert_to_openai_tool
from mcn_incubation.domain import IncubationProject, ProjectTruth, SubjectKind, TruthKind
from mcn_incubation.persistence import IncubationRepository
from mcn_incubation.persistence_schema import bootstrap_incubation_schema, read_incubation_schema_version
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.deps import _initialize_incubation_runtime
from deerflow.tools.builtins.incubation_project_context_tool import incubation_project_context_tool
from deerflow.tools.tools import BUILTIN_TOOLS

NOW = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
PROJECT_CONTEXT_MODULE = importlib.import_module("deerflow.tools.builtins.incubation_project_context_tool")


def _runtime(user_id: str) -> ToolRuntime:
    return ToolRuntime(
        state={"sandbox": {}, "thread_data": {}},
        context={"user_id": user_id, "thread_id": "thread-a"},
        config={"configurable": {"thread_id": "thread-a"}},
        stream_writer=lambda _: None,
        tools=[],
        tool_call_id="call-a",
        store=None,
    )


@pytest.mark.asyncio
async def test_project_context_reads_typed_current_truth_without_exposing_owner(monkeypatch, tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'incubation.db'}")
    await bootstrap_incubation_schema(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = IncubationRepository(session_factory)
    try:
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
        await repository.append_truth(
            ProjectTruth(
                truth_id="truth-a",
                owner_id="owner-a",
                project_id="project-a",
                kind=TruthKind.USER_FACT,
                statement="本人有八年企业财务经验",
                created_at=NOW,
                source_ref="user-interview-2026-08-11",
                evidence_refs=("resume-redacted.pdf",),
            ),
            operation_key="append-truth",
        )
        monkeypatch.setattr(PROJECT_CONTEXT_MODULE, "get_session_factory", lambda: session_factory)

        result = await incubation_project_context_tool.coroutine(_runtime("owner-a"), "project-a")
        other_owner_result = await incubation_project_context_tool.coroutine(_runtime("owner-b"), "project-a")

        assert result == {
            "authority": "project_truth_ledger",
            "project_id": "project-a",
            "truths": [
                {
                    "truth_id": "truth-a",
                    "kind": "user_fact",
                    "statement": "本人有八年企业财务经验",
                    "created_at": NOW.isoformat(),
                    "source_ref": "user-interview-2026-08-11",
                    "evidence_refs": ["resume-redacted.pdf"],
                }
            ],
            "note": "Keep each truth's kind and source boundary; unknowns and hypotheses are not verified facts.",
        }
        assert other_owner_result["truths"] == []
        assert "owner-a" not in repr(result)
    finally:
        await engine.dispose()


def test_project_context_is_read_only_builtin_with_runtime_owned_identity() -> None:
    parameters = convert_to_openai_tool(incubation_project_context_tool)["function"]["parameters"]

    assert incubation_project_context_tool in BUILTIN_TOOLS
    assert set(parameters["properties"]) == {"project_id"}
    assert "owner_id" not in parameters["properties"]


@pytest.mark.asyncio
async def test_project_context_reports_disabled_durable_storage(monkeypatch) -> None:
    monkeypatch.setattr(PROJECT_CONTEXT_MODULE, "get_session_factory", lambda: None)

    result = await incubation_project_context_tool.coroutine(_runtime("owner-a"), "project-a")

    assert result == {
        "authority": "project_truth_ledger",
        "project_id": "project-a",
        "truths": [],
        "status": "unavailable",
        "note": "Durable project truth is unavailable for this runtime; do not replace it with chat memory or guesses.",
    }


@pytest.mark.asyncio
async def test_gateway_initializes_incubation_schema_on_the_shared_database(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'gateway.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    try:
        await _initialize_incubation_runtime(
            app,
            engine=engine,
            session_factory=session_factory,
        )

        assert isinstance(app.state.incubation_repository, IncubationRepository)
        assert await read_incubation_schema_version(engine) == 2
    finally:
        await engine.dispose()
