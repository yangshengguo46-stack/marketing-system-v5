"""Read-only method context for the single DeerFlow incubation lead agent."""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.tools import tool
from mcn_incubation.methods import default_method_library

_METHOD_LIBRARY = default_method_library()


@tool(parse_docstring=True)
def incubation_context(query: str, limit: int = 4) -> dict:
    """Retrieve reviewed incubation methods relevant to the current judgment.

    The returned cards are advisory context. They do not select a strategy,
    enforce a workflow, mutate project truth, or replace the lead agent's
    judgment. Use the user's concrete business question as the query.

    Args:
        query: Current incubation question, including the material goal or unknown.
        limit: Maximum number of method cards to return, from 1 through 10.
    """

    if not query.strip():
        raise ValueError("query cannot be blank")
    if not 1 <= limit <= len(_METHOD_LIBRARY.cards):
        raise ValueError(f"limit must be between 1 and {len(_METHOD_LIBRARY.cards)}")
    cards = _METHOD_LIBRARY.search(query=query, limit=limit)
    methods = [
        {
            "method_card_id": card.method_card_id,
            "version": card.version,
            "capability": card.capability,
            "title": card.title,
            "applies_when": list(card.applies_when),
            "lens": list(card.lens),
            "evidence_needs": list(card.evidence_needs),
            "counterexamples": list(card.counterexamples),
            "source_refs": list(card.source_refs),
        }
        for card in cards
    ]
    source_refs = tuple(dict.fromkeys(source_ref for card in cards for source_ref in card.source_refs))
    as_of = datetime.now(UTC)
    resolved_sources = _METHOD_LIBRARY.source_catalog.resolve(source_refs)
    sources = [
        {
            "source_id": source.source_id,
            "kind": source.kind.value,
            "title": source.title,
            "locator": source.locator,
            "publisher": source.publisher,
            "retrieved_at": source.retrieved_at.isoformat(),
            "reviewed_at": source.reviewed_at.isoformat(),
            "status": source.status.value,
            "applicable_platforms": list(source.applicable_platforms),
            "applicable_regions": list(source.applicable_regions),
            "source_updated_label": source.source_updated_label,
            "refresh_after": source.refresh_after.isoformat() if source.refresh_after else None,
            "refresh_due": source.is_refresh_due(as_of=as_of),
            "supported_claims": list(source.supported_claims),
            "limitations": list(source.limitations),
        }
        for source in resolved_sources
    ]
    warnings = [f"Source {source.source_id} is due for refresh; verify it through a visible browser or approved evidence connector before treating it as current." for source in resolved_sources if source.is_refresh_due(as_of=as_of)]
    return {
        "authority": "advisory_context_only",
        "methods": methods,
        "sources": sources,
        "source_as_of": as_of.isoformat(),
        "warnings": warnings,
        "note": ("Apply only the lenses that materially change the current decision." if methods else "No reviewed method card matched; continue from current facts and state the unknown."),
    }


incubation_context_tool = incubation_context

__all__ = ["incubation_context_tool"]
