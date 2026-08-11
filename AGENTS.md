# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Codex, and others) when working with code in this repository. It is the source of truth; the sibling `CLAUDE.md` imports it via `@AGENTS.md`.

It is the **monorepo orientation layer**: it maps the whole repo and points to the
module guides that own the depth. For anything inside a module, read that module's
guide rather than expecting full detail here:

- **[backend/AGENTS.md](backend/AGENTS.md)** — backend depth: harness/app split, agent &
  middleware chain, sandbox, MCP, skills, memory, IM channels, persistence/migrations,
  config system, test layout.
- **[frontend/AGENTS.md](frontend/AGENTS.md)** — frontend depth: Next.js App Router layout,
  thread/streaming data flow, code style, commands.

## What is DeerFlow

DeerFlow is a LangGraph-based AI super-agent system with a full-stack architecture. The
backend runs a "super agent" with sandboxed execution, persistent memory, subagent
delegation, and extensible tools (built-in, MCP, community), all per-thread isolated. The
frontend is a Next.js chat UI. External IM platforms (Feishu, Slack, Telegram, Discord,
DingTalk) bridge into the same agent through the Gateway.

## Service Topology

A single `make dev` / Docker stack runs four cooperating services:

| Service         | Port   | Role                                                                 |
| --------------- | ------ | ------------------------------------------------------------------- |
| **Nginx**       | `2026` | Unified reverse-proxy entry point — open this in the browser        |
| **Gateway API** | `8001` | FastAPI REST API + embedded LangGraph-compatible agent runtime      |
| **Frontend**    | `3000` | Next.js web interface                                               |
| **Provisioner** | `8002` | Optional — only when sandbox is configured for provisioner/K8s mode |

Nginx is the single public entry: it serves the frontend and proxies `/api/langgraph/*`
to the Gateway's LangGraph runtime, rewriting it to Gateway's native `/api/*` routes; all
other `/api/*` go straight to the Gateway REST routers. See
[backend/AGENTS.md](backend/AGENTS.md) for the runtime and router detail.
It compresses HTML and configured textual assets, while deliberately leaving SSE,
fonts, images, audio, and video uncompressed at the proxy layer.

Both compose files publish that entry as `"${BIND_HOST:-127.0.0.1}:${PORT:-2026}:2026"`
— **loopback by default**, matching the README's documented deployment model. A bare
`"${PORT}:2026"` binds `0.0.0.0`, which does not.
Nginx itself listens `default_server` on IPv4+IPv6 and the
Gateway binds `0.0.0.0:8001` inside the container on purpose — both are container-
internal; the published nginx port is the entire external surface, and the Gateway's
`8001` is deliberately not published. Any new published port needs an explicit bind
address; `backend/tests/test_compose_default_bind_host.py` pins this for every service
in both compose files.

## Repository Map

```
deer-flow/
├── Makefile                        # Root orchestration: drives the full stack (dev/start/stop, docker, setup)
├── config.example.yaml             # Template → copy to config.yaml (gitignored) at repo root
├── extensions_config.example.json  # Template → copy to extensions_config.json (gitignored): MCP servers + skills
├── backend/                        # Python backend — see backend/AGENTS.md
│   ├── Makefile                    # Per-module backend commands (dev, gateway, test, lint, migrate-rev)
│   ├── packages/extension-api/     # deerflow-extension-api package (import: deerflow_extension_api.*) — public extension contract
│   ├── packages/mcn-incubation-core/ # fifth-version incubation contracts (import: mcn_incubation.*)
│   ├── packages/harness/           # deerflow-harness package (import: deerflow.*) — agent framework
│   └── app/                        # FastAPI Gateway + IM channels (import: app.*)
├── frontend/                       # Next.js frontend (pnpm) — see frontend/AGENTS.md
├── docker/                         # docker-compose files, nginx config, provisioner
├── skills/                         # Agent skills: public/ (committed), custom/ (gitignored)
│                                    # Managed integration skill packs are global at .deer-flow/integrations/skills/{provider}/
│                                    # Integration credentials and enabled state remain per-user
├── contracts/                      # Cross-component JSON contracts (e.g. subagent status, skill review)
├── scripts/                        # Root orchestration scripts invoked by the Makefile (check, configure, doctor, support_bundle, serve, nginx, docker, deploy, setup_wizard)
├── tests/                          # Root-level tests (currently tests/skills/ — public skill tests)
└── docs/                           # Cross-cutting docs, plans, and design notes
    ├── marketing-os/              # legacy/historical Marketing OS work; not the fifth-version product root
    └── mcn-incubation-v5/         # fifth-version incubation product contract, audits, eval corpus, and decisions
```

Third-party extensions are loaded from a top-level `plugins:` list in `config.yaml`
(operator-controlled on purpose — that list causes code to be imported, so it is deliberately
kept out of the API-writable `extensions_config.json`). See the Extension System section in
[backend/AGENTS.md](backend/AGENTS.md).

Runtime config lives at the **repo root**: copy `config.example.yaml` → `config.yaml`
(main app config) and `extensions_config.example.json` → `extensions_config.json` (MCP
servers + skills). Both real files are gitignored and may be edited at runtime via the
Gateway API. Config schema and resolution order are documented in
[backend/AGENTS.md](backend/AGENTS.md).

Skill quality review note:
- `skills/public/skill-reviewer/` is the built-in read-only skill quality reviewer.
  It uses the harness-layer `review_skill_package` tool and contracts in
  `contracts/skill_review/`. Model-visible review data is compact and
  tag-neutralized; full raw payloads stay in tool artifacts. See
  [backend/AGENTS.md](backend/AGENTS.md) for the non-activation, SkillScan, and
  `skill-creator` ownership boundaries.

Scheduled-task note:
- The scheduled-task MVP adds a workspace page at `/workspace/scheduled-tasks` plus a background scheduler service gated by `config.yaml -> scheduler.enabled`.
- Scheduled background runs are intentionally non-interactive: they execute through the normal run lifecycle, but the lead-agent toolset excludes `ask_clarification` and `incubation_record_subject_answer` when `context.non_interactive=true`. The key is honored only for internally-authenticated callers (the scheduler launch path); client-supplied `context.non_interactive` is dropped.

## Commands: Root vs. Module

**Root `make` targets drive the whole stack** (run from the repo root):

```bash
make setup       # Interactive setup wizard (recommended for new users)
make doctor      # Check configuration and system requirements
make support-bundle  # Generate redacted troubleshooting summary, AI issue draft, and optional zip
make config      # Generate local config files from the examples
make check       # Check that required tools are installed
make install     # Install all dependencies (frontend + backend + pre-commit hooks)
make dev         # Start all services with hot-reload (Gateway + Frontend + Nginx)
make start       # Start all services in production mode (local, optimized)
make stop        # Stop all running services
make up / down   # Build/stop the production Docker stack (browser at localhost:2026)
make docker-start / docker-stop / docker-logs   # Docker development environment
```

Docker log and restart commands resolve `DEER_FLOW_ROOT` from the current
checkout before invoking Compose, matching the start and stop commands.

Run `make help` for the full list.

**Per-module commands drive a single module** (run inside that module):

```bash
# Backend (see backend/AGENTS.md for the full set)
cd backend && make dev        # Gateway API with reload (port 8001)
cd backend && make test       # Backend test suite
cd backend && make lint       # ruff check
cd backend && make format     # ruff format

# Frontend (see frontend/AGENTS.md for the full set)
cd frontend && pnpm dev       # Dev server with Turbopack (port 3000)
cd frontend && pnpm check     # Lint + type check (run before committing)
cd frontend && pnpm test      # Unit tests
```

Rule of thumb: **root `make` = the full application**; **`backend/Makefile` and `frontend/`
(`pnpm`) = per-module work.**

Host-side pnpm consumers, including the root/frontend Makefiles and local diagnostic scripts, must run through `scripts/pnpm.py`. The runner preserves direct `pnpm`/`pnpm.cmd` priority, falls back to `corepack pnpm`, and is invoked from `frontend/` so Corepack honors the package-manager version pinned by that project.

## Where to Go Next

- Backend work → **[backend/AGENTS.md](backend/AGENTS.md)**
- Frontend work → **[frontend/AGENTS.md](frontend/AGENTS.md)**
- Setup & install → **[Install.md](Install.md)**, **[CONTRIBUTING.md](CONTRIBUTING.md)**
- Project overview & usage → **[README.md](README.md)** (translations: `README_zh.md`,
  `README_ja.md`, `README_fr.md`, `README_ru.md`)
- Security policy → **[SECURITY.md](SECURITY.md)**
- Changes → **[CHANGELOG.md](CHANGELOG.md)**
- Cutting a release → **[RELEASING.md](RELEASING.md)**

## Cross-Cutting Conventions

These apply repo-wide; module guides own the module-specific detail.

- **Documentation update policy** — keep docs in sync with code: update `README.md` for
  user-facing changes and the relevant `AGENTS.md` for development/architecture changes in
  the same change set.
- **Test-driven development** — features and bug fixes ship with tests. Backend tests live
  in `backend/tests/` (TDD is mandatory there; see [backend/AGENTS.md](backend/AGENTS.md));
  frontend tests live in `frontend/tests/`.
- **Legacy Marketing OS evidence** — `docs/marketing-os/` is an archived audit
  record, not the current product contract. Its abandoned runtime package and
  Gateway projection are deliberately absent. Use the audits for provenance and
  failure lessons; do not restore them as a wrapper around the fifth version.
- **Fifth-version incubation delivery** — DeerFlow's single Lead Agent is the
  incubation decision-maker. Read `docs/mcn-incubation-v5/` before changing
  `packages/mcn-incubation-core` or the Lead Agent prompt. Do not add another
  agent runtime, semantic middleware, fixed incubation stage, or score gate.
  New fifth-version work must not depend on the legacy `marketing-os` package.
  V4 Skills follow audit A30: strategy and platform judgment is distilled into
  sourced method cards, evidence/content craft may be loaded one package at a
  time only after focused evaluation, and retired orchestration or cinematic
  systems are never bulk-copied. V4 account-decomposition code is a source of
  identity, coverage, provenance, and failure-test semantics, not a runtime
  dependency or an account-verdict compiler.
  Audit A31 pins the first full-agent failure repair: broad method queries may
  retrieve up to six bounded lenses, platform-program sources cannot establish
  project fit or priority, and observed failures become sourced method
  counterexamples rather than new prompt gates. A33 records that the approved
  paid v4 retest skipped the available method tool and again failed business
  review. M01 remains business-rejected; do not force a method-tool trajectory
  or spend another paid trial before a new offline hypothesis passes.
  Audit A34 pins the next offline repair: ask only for subject facts that could
  reverse a recommendation, and do not promote a familiar or cheap format from
  candidate to primary without performance, proof, resource, privacy, and
  sustainable-supply evidence. Full-agent evaluations must disable general
  DeerMem reads and writes in an isolated config copy; project truth still lives
  in the typed ledger. Do not turn this into a fixed intake form or stage gate.
  Audit A35 records that the paid v5 initial and mutation answers both failed
  business review even after reading methods. It also invalidates the old
  isolated mutation design: revisions must append evidence to the same project
  and resume the same thread. Do not claim revision ability from v5 or run
  another paid trial before the sequential harness and subject-discovery
  expectations pass offline.
  Audit A36 governs public vertical-agent reuse: keep DeerFlow as the only
  runtime, distill isolated context/evidence/feedback patterns only after
  focused evaluation, and treat fixed-stage marketing agencies or large
  persona/skill teams as architecture counterexamples rather than migration
  targets.
  Audit A37 and proposed ADR-009 clarify that one incubation authority does
  not require one model invocation: the Lead remains the only user-facing
  decision-maker, while bounded read-only subagents may be evaluated through
  DeerFlow's existing `task` tool as agents-as-tools. Do not use handoffs,
  force delegation, give a subagent project writes, or register a department
  of strategy personas. The first evidence specialist exists only in an
  isolated capped evaluator until business outcomes justify adoption.
  Audit A38 owns subject-answer provenance. The Lead-only
  `incubation_record_subject_answer` tool reads the original question and exact
  user reply from the current structured human-input run, derives ownership
  from runtime identity, and appends a versioned `ProjectTruth`. Models must not
  supply answer text or owner identity; subagents cannot write; approvals are
  never subject facts. This is provenance capture, not a fixed questionnaire or
  required tool route.
  Audit A42 keeps marketing-territory work experimental. `TerritoryCandidate`
  is an optional record inside the existing decision JSON, not a stage or model
  output contract. The isolated method, source-mechanism, and two-pass contexts
  all remain outside production after 24 technically complete but
  business-rejected trials; do not wire them into the Lead prompt or default
  method library. A two-pass evaluation consumes two paid model calls and still
  leaves the Lead as the sole decision authority.
  Audit A43 and proposed ADR-011 separate content-world discovery, marketing
  selection, and narrative craft. Upward abstraction, downward decomposition,
  horizontal expansion, and cross-domain connection are optional candidate
  operators, not a required four-step workflow or a Charlie-course quotation.
  Do not route them by industry keywords, register the evaluation-only
  `content-world-exploration-v1`, or add a vector database before cross-case
  evaluation. Model parametric knowledge may suggest hypotheses; historical,
  cultural, media, industry, and current claims need browser/MCP evidence before
  promotion. Charlie-derived craft may shape a selected node into a story, but
  it does not own incubation judgment and must not restore the cinematic-IP
  product stack.
  Audits A44-A45 reject the first direct single-pass operator card and trace its
  B2B/B2C/industry-account outputs. The sealed request contained exactly one
  system message and one user message, with no tools, history, skills, V4 code,
  or full DeerFlow prompt. The evaluation itself mixed the canonical complete
  incubation contract, final customer-delivery pressure, and world exploration;
  a generic model prior then remained the best-supported explanation for the
  stock taxonomy. Preserve that failed card as evidence. The evaluation-only
  `content_world_exploration` response mode removes final strategy pressure and
  compares a plain read-only explorer with a conversation-v2 operator card. Do
  not import either explorer context into the production Lead, methods, or
  knowledge catalog, and do not execute another paid run without fresh user
  approval.
  Audit A46 separately records the user's explicit production trial of the
  corrected idea. The compact `MARKETING_WORLD_THINKING_CONTRACT` belongs to the
  existing Lead contract, contains no domain answer examples, keeps the four
  expansion lenses optional, and distinguishes positioning, content, and
  expression form. Pure world-opening requests temporarily defer subject-fit
  and full-plan delivery; complete incubation work still uses project facts.
  This is an offline-tested prompt hypothesis, not a business-quality pass, and
  it does not promote either rejected evaluator context.
  Audit A47 updates that validation record: a zero-token overlong-thread failure
  was preserved, the bounded-ID production rerun completed `2/2` with 64,005
  tokens, and both answers failed business review. Gold still centered gold
  rather than gift-giving; fruit lifecycle was only a partial signal. Both cases
  retrieved the broad `content-engine-v1` and `incubation-model-v1` cards, but
  renewed full-incubation pressure remains an inference for offline audit. Do
  not force a route or start another paid run without fresh user approval.
  Audit A32 owns the host-independent account-decomposition evidence objects.
  Missing identity, coverage, metrics, media atoms, or counterexamples remain
  explicit warnings; cross-account references and unconsented cloud receipts
  are integrity failures. The module must not grow verdict, score, fixed sample,
  or incubation-decision fields.
- **Format before pushing** — run `make format` (backend) / `pnpm check` (frontend). Backend
  CI enforces `ruff format --check`, so formatting must be clean before a push.
