# mcn-incubation-core

Internal, host-independent business contracts for the fifth-version DeerFlow incubation agent. This is a technical codename, not the public product name.

DeerFlow's existing Lead Agent is the only incubation decision-maker. This package supplies immutable project facts, versioned decisions, experiments, observed outcomes, reviewed case memory, method cards, and the architecture bakeoff protocol. It does not contain an agent runtime, workflow engine, platform publisher, media pipeline, or model-output middleware.

`mcn_incubation.agent_contract.INCUBATION_AGENT_CONTRACT` is the canonical thin incubation contract shared verbatim by the production Lead Agent and evaluation context assembler. Do not copy or fork it into another prompt.

The DeerFlow harness exposes three read-only tools backed by this package. `incubation_context` returns relevant reviewed method cards plus typed source metadata, applicability, freshness controls, supported claims, and limitations. `incubation_project_context` reads only the authenticated owner's unsuperseded project truths while preserving each truth kind and source boundary. `incubation_project_evidence` separately reads current evidence snapshots with provenance, content hashes, scope, limitations, dispute state, and expiry warnings. None of these tools selects a strategy or mutates project state.

`mcn_incubation.preflight` provides the host-independent append-only evidence ledger used by `backend/scripts/run_incubation_preflight.py`. It seals prompt and output hashes, normalized usage, failure codes, and completion integrity without storing credentials or treating provider fallback text as a business answer.

`backend/scripts/run_incubation_micro_bakeoff.py` reuses that ledger to compare explicitly selected context architectures through the configured DeerFlow model with one hard paid-trial cap. It is evaluation tooling rather than an agent runtime. The reviewed-case candidate fails closed until genuine outcome-backed, human-reviewed cases exist.

`backend/scripts/run_incubation_agent_eval.py` is the next full-Agent evaluation path. It seeds each selected case into an isolated project/evidence database, runs the existing `DeerFlowClient` with an in-memory checkpoint, and seals the configured tool schemas, redacted tool trajectory, output, usage, and database digest. It requires explicit trial and recursion limits plus `--execute`; neither limit is represented as an exact currency cap.

`backend/scripts/run_marketing_territory_bakeoff.py` also contains evaluation-only content-territory candidates. The failed conversation-v1 operator card is retained for provenance. `ResponseMode.CONTENT_WORLD_EXPLORATION` isolates a read-only world-mapping task from the canonical production Lead and final customer-delivery contracts; its baseline and conversation-v2 variants differ only by the operator card. This mode is not registered in production and has no paid-model result.

Run the focused tests from `backend/`:

```bash
uv run python -m pytest tests/mcn_incubation_tests tests/test_incubation_context_tool.py tests/test_incubation_project_context_tool.py tests/test_incubation_project_evidence_tool.py -q
```
