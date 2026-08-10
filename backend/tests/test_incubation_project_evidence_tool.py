from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest
from langchain.tools import ToolRuntime
from langchain_core.utils.function_calling import convert_to_openai_tool
from mcn_incubation.domain import (
    EvidenceItem,
    EvidenceKind,
    EvidenceStatus,
    IncubationProject,
    SubjectKind,
)
from mcn_incubation.persistence import IncubationRepository
from mcn_incubation.persistence_schema import bootstrap_incubation_schema
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from deerflow.tools.builtins.incubation_project_evidence_tool import (
    incubation_project_evidence_tool,
)
from deerflow.tools.tools import BUILTIN_TOOLS

CAPTURED_AT = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)
AS_OF = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
EVIDENCE_MODULE = importlib.import_module("deerflow.tools.builtins.incubation_project_evidence_tool")


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
async def test_project_evidence_is_owner_scoped_and_surfaces_staleness(
    monkeypatch,
    tmp_path,
) -> None:
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
                created_at=CAPTURED_AT,
            ),
            operation_key="create-project",
        )
        await repository.append_evidence(
            EvidenceItem(
                evidence_id="evidence-a",
                owner_id="owner-a",
                project_id="project-a",
                kind=EvidenceKind.OFFICIAL_PLATFORM_SNAPSHOT,
                status=EvidenceStatus.CONTESTED,
                source_locator=("https://user:secret@example.test/platform-rule?access_token=secret#fragment"),
                captured_at=CAPTURED_AT,
                content_hash="a" * 64,
                observed_facts=("页面声明商业内容需要披露合作关系",),
                limitations=("页面只描述商业内容场景",),
                artifact_refs=("artifact://evidence-a.html",),
                applicable_platforms=("tiktok",),
                applicable_regions=("US",),
                source_updated_label="updated 2026-08-01",
                expires_at=datetime(2026, 8, 11, 10, 0, tzinfo=UTC),
            ),
            operation_key="append-evidence",
        )
        monkeypatch.setattr(EVIDENCE_MODULE, "get_session_factory", lambda: session_factory)
        monkeypatch.setattr(EVIDENCE_MODULE, "_now_utc", lambda: AS_OF)

        result = await incubation_project_evidence_tool.coroutine(
            _runtime("owner-a"),
            "project-a",
            "tiktok",
            20,
        )
        other_owner_result = await incubation_project_evidence_tool.coroutine(
            _runtime("owner-b"),
            "project-a",
            "tiktok",
            20,
        )

        assert result["authority"] == "project_evidence_ledger"
        assert result["as_of"] == AS_OF.isoformat()
        assert result["evidence"] == [
            {
                "evidence_id": "evidence-a",
                "kind": "official_platform_snapshot",
                "status": "contested",
                "source_locator": "https://example.test/platform-rule",
                "captured_at": CAPTURED_AT.isoformat(),
                "content_hash": "a" * 64,
                "observed_facts": ["页面声明商业内容需要披露合作关系"],
                "limitations": ["页面只描述商业内容场景"],
                "artifact_refs": ["artifact://evidence-a.html"],
                "applicable_platforms": ["tiktok"],
                "applicable_regions": ["US"],
                "source_updated_label": "updated 2026-08-01",
                "expires_at": datetime(2026, 8, 11, 10, 0, tzinfo=UTC).isoformat(),
                "refresh_due": True,
            }
        ]
        assert result["warnings"] == [
            "evidence-a is contested; preserve the disagreement.",
            "evidence-a is due for refresh; do not present it as current.",
        ]
        assert other_owner_result["evidence"] == []
        assert "owner-a" not in repr(result)
        assert "secret" not in repr(result)
    finally:
        await engine.dispose()


def test_project_evidence_is_read_only_builtin_with_runtime_owned_identity() -> None:
    parameters = convert_to_openai_tool(incubation_project_evidence_tool)["function"]["parameters"]

    assert incubation_project_evidence_tool in BUILTIN_TOOLS
    assert set(parameters["properties"]) == {"project_id", "platform", "limit"}
    assert "owner_id" not in parameters["properties"]


@pytest.mark.asyncio
async def test_project_evidence_reports_disabled_durable_storage(monkeypatch) -> None:
    monkeypatch.setattr(EVIDENCE_MODULE, "get_session_factory", lambda: None)

    result = await incubation_project_evidence_tool.coroutine(
        _runtime("owner-a"),
        "project-a",
        None,
        20,
    )

    assert result == {
        "authority": "project_evidence_ledger",
        "project_id": "project-a",
        "evidence": [],
        "status": "unavailable",
        "note": "Durable project evidence is unavailable; do not replace it with chat memory, browser state, or guesses.",
    }


@pytest.mark.asyncio
async def test_project_evidence_rejects_unbounded_reads() -> None:
    with pytest.raises(ValueError, match="limit"):
        await incubation_project_evidence_tool.coroutine(
            _runtime("owner-a"),
            "project-a",
            None,
            101,
        )
