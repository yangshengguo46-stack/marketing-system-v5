"""Owner-scoped project truth for the single incubation lead agent."""

from __future__ import annotations

from langchain.tools import tool
from mcn_incubation.persistence import IncubationRepository

from deerflow.persistence.engine import get_session_factory
from deerflow.runtime.user_context import resolve_runtime_user_id
from deerflow.tools.types import Runtime


@tool(parse_docstring=True)
async def incubation_project_context(runtime: Runtime, project_id: str) -> dict:
    """Read the current typed facts for one incubation project.

    This is the canonical project-state reader. It returns only unsuperseded
    truth records and preserves whether each item is a fact, inference,
    hypothesis, unknown, decision, or observed outcome. It never writes state
    or chooses an incubation strategy.

    Args:
        project_id: Project whose current truth ledger is needed.
    """

    if not project_id.strip():
        raise ValueError("project_id cannot be blank")
    session_factory = get_session_factory()
    if session_factory is None:
        return {
            "authority": "project_truth_ledger",
            "project_id": project_id,
            "truths": [],
            "status": "unavailable",
            "note": "Durable project truth is unavailable for this runtime; do not replace it with chat memory or guesses.",
        }

    owner_id = resolve_runtime_user_id(runtime)
    truths = await IncubationRepository(session_factory).list_current_truths(
        owner_id=owner_id,
        project_id=project_id,
    )
    return {
        "authority": "project_truth_ledger",
        "project_id": project_id,
        "truths": [
            {
                "truth_id": truth.truth_id,
                "kind": truth.kind.value,
                "statement": truth.statement,
                "created_at": truth.created_at.isoformat(),
                "source_ref": truth.source_ref,
                "evidence_refs": list(truth.evidence_refs),
            }
            for truth in truths
        ],
        "note": "Keep each truth's kind and source boundary; unknowns and hypotheses are not verified facts.",
    }


incubation_project_context_tool = incubation_project_context

__all__ = ["incubation_project_context_tool"]
