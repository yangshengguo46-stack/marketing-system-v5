"""Owner-scoped evidence snapshots for the single incubation lead agent."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from langchain.tools import tool
from mcn_incubation.domain import EvidenceStatus
from mcn_incubation.persistence import IncubationRepository

from deerflow.persistence.engine import get_session_factory
from deerflow.runtime.user_context import resolve_runtime_user_id
from deerflow.tools.types import Runtime


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _safe_locator(locator: str) -> str:
    parsed = urlsplit(locator)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return locator
    host = parsed.hostname
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


@tool(parse_docstring=True)
async def incubation_project_evidence(
    runtime: Runtime,
    project_id: str,
    platform: str | None = None,
    limit: int = 20,
) -> dict:
    """Read current external evidence snapshots for one incubation project.

    Evidence remains distinct from verified project truth and from incubation
    decisions. The result preserves provenance, scope, limitations, disputes,
    and staleness, and never writes project state.

    Args:
        project_id: Project whose current evidence snapshots are needed.
        platform: Optional platform scope such as tiktok or xiaohongshu.
        limit: Maximum number of current snapshots to return, from 1 to 100.
    """

    if not project_id.strip():
        raise ValueError("project_id cannot be blank")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if platform is not None and not platform.strip():
        raise ValueError("platform cannot be blank when supplied")

    session_factory = get_session_factory()
    if session_factory is None:
        return {
            "authority": "project_evidence_ledger",
            "project_id": project_id,
            "evidence": [],
            "status": "unavailable",
            "note": "Durable project evidence is unavailable; do not replace it with chat memory, browser state, or guesses.",
        }

    owner_id = resolve_runtime_user_id(runtime)
    evidence_items = await IncubationRepository(session_factory).list_current_evidence(
        owner_id=owner_id,
        project_id=project_id,
        platform=platform,
        limit=limit,
    )
    as_of = _now_utc()
    warnings: list[str] = []
    evidence_payloads: list[dict] = []
    for evidence in evidence_items:
        refresh_due = evidence.is_refresh_due(as_of=as_of)
        if evidence.status is EvidenceStatus.CONTESTED:
            warnings.append(f"{evidence.evidence_id} is contested; preserve the disagreement.")
        if refresh_due:
            warnings.append(f"{evidence.evidence_id} is due for refresh; do not present it as current.")
        evidence_payloads.append(
            {
                "evidence_id": evidence.evidence_id,
                "kind": evidence.kind.value,
                "status": evidence.status.value,
                "source_locator": _safe_locator(evidence.source_locator),
                "captured_at": evidence.captured_at.isoformat(),
                "content_hash": evidence.content_hash,
                "observed_facts": list(evidence.observed_facts),
                "limitations": list(evidence.limitations),
                "artifact_refs": list(evidence.artifact_refs),
                "applicable_platforms": list(evidence.applicable_platforms),
                "applicable_regions": list(evidence.applicable_regions),
                "source_updated_label": evidence.source_updated_label,
                "expires_at": (evidence.expires_at.isoformat() if evidence.expires_at else None),
                "refresh_due": refresh_due,
            }
        )

    return {
        "authority": "project_evidence_ledger",
        "project_id": project_id,
        "platform": platform,
        "as_of": as_of.isoformat(),
        "evidence": evidence_payloads,
        "warnings": warnings,
        "note": "Evidence snapshots are observations, not automatically verified project truths or incubation decisions.",
    }


incubation_project_evidence_tool = incubation_project_evidence

__all__ = ["incubation_project_evidence_tool"]
