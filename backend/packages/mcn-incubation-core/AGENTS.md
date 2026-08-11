# MCN Incubation Core Guide

Read `docs/mcn-incubation-v5/current/PRODUCT_CONTRACT.md` and the A20-A51 audits before changing this package.

## Ownership

- DeerFlow's Lead Agent owns the sole incubation decision authority and the final user-facing recommendation. A bounded read-only subagent may return advisory evidence through the existing `task` tool, but never owns project state or a recommendation.
- This package owns data contracts, owner-scoped persistence, reviewed method cards, selective case recall, context comparison, and evaluation records.
- Browser, audience, media, publication, and analytics capabilities are downstream tools. They may consume incubation decisions or return evidence, but cannot become decision-makers.

## Non-Negotiable Boundaries

- Do not add another agent runtime, handoff, semantic middleware, model-output rewrite, forced tool route, or fixed incubation stage. A37's evaluation-only evidence specialist must stay read-only, non-recursive, optional, and capped until ADR-009 is accepted.
- `agent_contract.INCUBATION_AGENT_CONTRACT` is the one canonical production/evaluation incubation contract. Import it; never maintain a copied prompt block.
- `IncubationRepository.list_current_truths` defines the model-visible truth heads: retain append-only history, but never return records superseded inside the same owner-scoped project.
- The built-in `incubation_project_context` reader derives ownership from authenticated `ToolRuntime`; never add a model-supplied `owner_id` argument or silently substitute chat memory when durable storage is unavailable.
- The Lead-only `incubation_record_subject_answer` writer may accept only `project_id` and a stable semantic `fact_key`; it must derive the owner, original question, and exact answer from the current structured human-input run, append a `ProjectTruth` version, and reject approvals. Keep it unavailable to every subagent and never turn it into a fixed intake route.
- `EvidenceItem` remains separate from `ProjectTruth`. The built-in `incubation_project_evidence` reader must preserve provenance, scope, limitations, contested status, and staleness; never add a model-supplied `owner_id`, raw browser session state, or an automatic evidence-to-truth promotion.
- Every production `MethodCard.source_refs` entry must resolve through `KnowledgeCatalog` to reviewed source metadata with supported claims and limitations. Platform sources require platform scope and a refresh date; do not universalize a narrow platform rule.
- Method retrieval tests may assert relevant capability recall and bounded results. They must not require a unique card, fixed rank, fixed tool route, or a permanent method-card count.
- Missing business information remains an explicit unknown and never becomes a completeness gate.
- Case memory requires observed outcomes and human review; cross-project recall is off by default.
- Deterministic code may calculate and validate objective integrity, not choose positioning, expression form, content direction, or monetization.
- Preflight records are append-only local evidence. Provider fallback messages and empty outputs are failures; incomplete runs cannot support an architecture decision.
- Micro-bakeoff runs must explicitly name cases and candidates, enforce a paid-call ceiling, use the same configured model and context budget, and seal every input and output. A one-case run can reject a candidate but cannot establish an architecture winner.
- A44-A45 preserve the business-rejected conversation-v1 content-world card and its exact prompt provenance. `ResponseMode.CONTENT_WORLD_EXPLORATION`, `CONTENT_WORLD_EXPLORATION_CONTEXT`, and the conversation-v2 operator card are evaluator-only task-isolation contracts; they must remain absent from the production Lead prompt, method library, and knowledge catalog. Their existence is not a passing model result, and another paid run requires fresh user authorization.
- A46 adds a distinct compact `MARKETING_WORLD_THINKING_CONTRACT` to the canonical Lead contract at the user's explicit direction. It separates positioning, content, and expression form and scopes pure world-opening requests away from subject-fit and full-plan delivery. Do not copy the rejected evaluation cards or domain examples into it, turn its optional lenses into ordered steps, permanently ignore subject facts in full incubation work, or describe the offline prompt test as business validation.
- A47 records the first real production-Lead trial of that compact contract. Preserve the zero-token overlong-thread failure and the repaired 64,005-token run separately. Technical completion was `2/2`, but both outputs were business-rejected; fruit lifecycle was only a partial signal and gold still centered gold instead of gift-giving. Both trials retrieved `content-engine-v1` and `incubation-model-v1`; method pressure is an unproven hypothesis for offline audit, not permission to force a tool route or rerun a paid model without fresh approval.
- A48 upgrades broad method context from an inference to a supported material interferer, not the sole failure cause. Its historical `method_context_mode=disabled` path remains a single-Lead content-world ablation; A51 extends that evaluator-only switch solely to the sealed shared-chain single-Lead/team comparison. It must not become a production keyword route or global method deletion.
- A51 adds a separate evaluator-only shared marketing chain and `marketing-reasoning-team`; it does not replace `agent_contract.py`, enter the method library, or register production subagents. The matched gold-gift team and single Lead were both business-rejected, with the single Lead closer to the expert anchor and the team slower, more expensive, and more industry-generic. Preserve both outputs as evidence; do not promote this five-way parallel decomposition or repair it by adding roles, quotas, rankings, or another runtime.
- Full Agent evaluation runs must use the existing `DeerFlowClient`, an isolated evaluation database and in-memory checkpoint, explicit trial and recursion limits, and a redacted tamper-evident tool trace. Do not describe either limit as an exact currency cap, require a fixed tool route, or run paid trials without `--execute` and user confirmation.
- Do not test `thin_prompt_methods_truth_cases` with synthetic or merely authored examples. It requires observed outcomes plus human review under the case-memory contract.
- Add a failing behavior test before implementation and keep the public product name outside this internal package.
