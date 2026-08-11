# MCN Incubation Core Guide

Read `docs/mcn-incubation-v5/current/PRODUCT_CONTRACT.md` and the A20-A37 audits before changing this package.

## Ownership

- DeerFlow's Lead Agent owns the sole incubation decision authority and the final user-facing recommendation. A bounded read-only subagent may return advisory evidence through the existing `task` tool, but never owns project state or a recommendation.
- This package owns data contracts, owner-scoped persistence, reviewed method cards, selective case recall, context comparison, and evaluation records.
- Browser, audience, media, publication, and analytics capabilities are downstream tools. They may consume incubation decisions or return evidence, but cannot become decision-makers.

## Non-Negotiable Boundaries

- Do not add another agent runtime, handoff, semantic middleware, model-output rewrite, forced tool route, or fixed incubation stage. A37's evaluation-only evidence specialist must stay read-only, non-recursive, optional, and capped until ADR-009 is accepted.
- `agent_contract.INCUBATION_AGENT_CONTRACT` is the one canonical production/evaluation incubation contract. Import it; never maintain a copied prompt block.
- `IncubationRepository.list_current_truths` defines the model-visible truth heads: retain append-only history, but never return records superseded inside the same owner-scoped project.
- The built-in `incubation_project_context` reader derives ownership from authenticated `ToolRuntime`; never add a model-supplied `owner_id` argument or silently substitute chat memory when durable storage is unavailable.
- `EvidenceItem` remains separate from `ProjectTruth`. The built-in `incubation_project_evidence` reader must preserve provenance, scope, limitations, contested status, and staleness; never add a model-supplied `owner_id`, raw browser session state, or an automatic evidence-to-truth promotion.
- Every production `MethodCard.source_refs` entry must resolve through `KnowledgeCatalog` to reviewed source metadata with supported claims and limitations. Platform sources require platform scope and a refresh date; do not universalize a narrow platform rule.
- Method retrieval tests may assert relevant capability recall and bounded results. They must not require a unique card, fixed rank, fixed tool route, or a permanent method-card count.
- Missing business information remains an explicit unknown and never becomes a completeness gate.
- Case memory requires observed outcomes and human review; cross-project recall is off by default.
- Deterministic code may calculate and validate objective integrity, not choose positioning, expression form, content direction, or monetization.
- Preflight records are append-only local evidence. Provider fallback messages and empty outputs are failures; incomplete runs cannot support an architecture decision.
- Micro-bakeoff runs must explicitly name cases and candidates, enforce a paid-call ceiling, use the same configured model and context budget, and seal every input and output. A one-case run can reject a candidate but cannot establish an architecture winner.
- Full Agent evaluation runs must use the existing `DeerFlowClient`, an isolated evaluation database and in-memory checkpoint, explicit trial and recursion limits, and a redacted tamper-evident tool trace. Do not describe either limit as an exact currency cap, require a fixed tool route, or run paid trials without `--execute` and user confirmation.
- Do not test `thin_prompt_methods_truth_cases` with synthetic or merely authored examples. It requires observed outcomes plus human review under the case-memory contract.
- Add a failing behavior test before implementation and keep the public product name outside this internal package.
