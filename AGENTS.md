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
│   ├── packages/harness/           # deerflow-harness package (import: deerflow.*) — agent framework
│   ├── experiments/                # isolated experiments, never runtime by default
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
- Scheduled background runs are intentionally non-interactive: they execute through the normal run lifecycle, but the lead-agent toolset excludes `ask_clarification` when `context.non_interactive=true`. The key is honored only for internally-authenticated callers (the scheduler launch path); client-supplied `context.non_interactive` is dropped.

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
- **Fifth-version marketing brain** — ADR-007 targets a usable 80-point
  incubation judgment across marketing subject, positioning, content world,
  presentation format, monetization, and fact boundaries. This is not an
  80-percent video-understanding target. MediaKit and account extraction remain
  supporting evidence capabilities. The E15 implementation under
  `backend/experiments/` is isolated and must not be registered as a Lead tool,
  MCP server, or Skill before real-account acceptance is recorded.
  Its account-link boundary accepts only a user-supplied URL, an explicit
  collection method and rights reference, and a sample cap of at most 24 posts.
  Collectors return whitelisted profile/post observations; raw DOM/HTML,
  cookies, browser storage, temporary media URLs, and local paths are not part
  of the returned contract. This is an output boundary, not a prohibition on
  local credential use: account-scoped connectors may read Cookie/StorageState,
  including from trusted local Chrome over CDP, but credential values cannot
  enter model context, frontend payloads, logs, tests, search results, evidence
  snapshots, or MCP/Tool output. E15 targets content search, account search, and
  account post lists across Douyin, Xiaohongshu, WeChat Channels, Kuaishou,
  Bilibili, and TikTok. Five web adapters plus a WeChat desktop bridge contract
  remain experimental; platform-by-platform live acceptance, not enum coverage,
  determines support. The audience layer is named audience-intelligence
  collection, never comment collection: comments are only one interaction
  source beside account scale, growth, demographics, interests, activity,
  content interactions, live audience, and commerce affinity. Every dataset
  carries its own coverage receipt, and observed platform values, locally
  derived time-series metrics, third-party estimates, and HLLM inferences must
  remain distinct. Raw audience identifiers are pseudonymized before snapshots;
  only actor-linked behavior sequences may enter HLLM. Creator post history or
  aggregate post performance cannot impersonate audience behavior. The pinned
  HLLM adapter is a model boundary, not a collector, and cannot claim a real
  inference without a matching checkpoint receipt. Audience-source routing is
  official-first: authorized Douyin accounts use approved Open Platform data,
  content-collaboration research uses authenticated Xingtu evidence, and
  commerce matching uses authenticated Buyin/Selected Alliance evidence. Paid
  third-party analytics are optional cross-checks, never runtime prerequisites.
  Competitor-account analysis must not route to the authorized-account
  `fans.data` API; Xingtu competitor evidence is implemented and accepted first,
  while authorized-account APIs belong to the later own-account retrospective.
  Followers, content viewers, engagers, live viewers, and purchasers must retain
  distinct population scopes. A37, A38, and A40 own these
  experimental boundaries. Source snapshots are content-addressed locally. Even when
  the local evidence pack is large, the Lead-facing projection has a hard UTF-8
  byte budget (16 KB by default), contains only bounded candidate patterns,
  representative post/evidence IDs, coverage, limitations, and hashes, and
  treats all page text as untrusted evidence rather than instructions. Account,
  rights, and post identities must match before projection. A35 owns this
  experimental boundary. A39 records one passing real Douyin account sample:
  author-qualified recent posts, two local media records, two-post visible
  audience interactions, and a bounded Lead projection. This permits continued
  isolated research only; it does not register E15 or establish support for the
  other platforms. Account analysis must distinguish acquisition positioning,
  current positioning, migration evidence, and conditions that cannot be
  copied. A mature person-centric account cannot be presented as a cold-start
  category template.
  The default Lead may call the bounded `analyze_business_semantics` tool when
  a user's business expression needs semantic explication. For requests about
  starting or positioning an account or choosing a long-term content territory,
  it may call `explore_content_worlds`, which reads user-authored thread text,
  separates the commercial object, lexical head, and minimal complete content
  root, then expands one rooted map and returns a fact/response contract.
  Modifier decisions are derived from a removal counterfactual over world
  completeness, buyer-side constitutive function, and the return path to the
  commercial object; do not replace this with industry keyword rules. Neither tool is
  middleware or a workflow stage, and neither owns the final incubation
  decision. Semantic explication and content mapping must not design business
  operations; the overall Lead may handle that responsibility separately. Use
  positive contracts, not keyword gates: advertising or sales may themselves be
  legitimate business objects. The offline E28 candidate separates source object,
  audience world, content engines, and attention entries. It is not registered
  because its production probes did not pass. E29's isolated one-call candidate
  added rooted expansion nodes but passed only one of six frozen cases; ADR-009
  rejects that implementation for production. E30 separated skeleton selection from
  frozen-parent expansion and improved to three of six, but still failed the
  preregistered threshold and golden-gift semantic leap; ADR-010 rejects production
  promotion. Do not register these evaluators or infer production approval from a
  locally passing sample. A34 records the original object-map acceptance; A42 and
  ADR-008 own the newer account-level boundary, while A43-A44 and ADR-009-ADR-010
  own the layered-map rejections.
  A45 maps the next research boundary to qualia roles, means-end chains,
  Jobs-to-be-Done, frame semantics, concept bottlenecks, and causal models.
  Removal or substitution probes are semantic ablations over model behavior,
  not Pearl-style evidence of market causality. Any semantic concept-bottleneck
  candidate must remain optional, inspectable, and offline until a preregistered
  contrastive evaluation passes; it must not become another mandatory workflow.
  E31's full concept bottleneck did not pass: it surfaced the golden-gift
  gifting-practice leap but increased contract failures, unsupported detail,
  and theory-shaped over-abstraction during convergence. ADR-011 rejects that
  runtime architecture. Preserve candidate-recall versus final-convergence as
  an evaluation distinction only; do not register E31 or tune on its six cases.
  E32's separately preregistered nullable plain-language thin lattice did not
  pass: candidate recall was five of seven, final convergence three of seven,
  and only one of four held-out contrasts passed. It reduced contract failures
  and cost, and the gifting leap transferred across materials, but convergence
  still promoted ordinary use or production processes. ADR-012 rejects the
  independent two-call lattice for production. Do not tune or rerun its seven
  cases, expose hidden labels, or stack more prompts/agents onto it. Retain its
  thin-contract and recall/convergence/contrast diagnostics only.
  E33's relation-first replacement classified all four stay/change relations
  correctly but reached only six of eight candidate recalls and final roots.
  It also exposed a Chinese substring-scoring false negative and a seller-
  operation false positive; manual review found unsupported production and
  evidence assumptions. ADR-013 rejects E33 for production while retaining the
  relation-first primitive. A successor may add only the small distinction
  among complete object, seller operation/proof, buyer ordinary use, and buyer
  recurring social practice/result. It must use new cases and replace, not
  stack on, E33.
  E34's frozen actor-role successor also failed: relation judgment was three of
  four, role/disposition checks eleven of sixteen, candidate recall seven of
  eight, final convergence five of eight, and final contrasts two of four. Its
  only automatic all-pass pair contained a parent/child substring false
  positive and an option-binding contract loophole. Children's reading and
  custom shoemaking also showed that two hidden role labels were ambiguous.
  ADR-014 rejects E34 and the four roles as a mandatory bottleneck. Do not
  rerun, tune, register, or stack E34. Calibrate a user-reviewable annotation
  protocol with valid alternative roots before another prompt experiment.
  A50 now owns that six-case development annotation protocol as evaluation data
  only. E35/A51 compares a new single-call semantic candidate against the exact
  user-designated rollback baseline `ca2af9f8` on six new cases. Both arms have
  equal primary calls and hidden exact-alias review. Do not inject the six
  development annotations into either arm or infer production promotion from a
  semantic-only win.
  The one frozen E35 run did not pass its automatic exact-alias threshold.
  Although its first manual review found scorer false negatives, E36 then ran
  the unchanged prompt against the four user-corrected fruit, golden-gift,
  seafood, and hot-pot-base cases. Semantic migration and rooted content-map
  acceptance were both `0/4`. ADR-016 therefore supersedes ADR-015's adoption
  direction: actions, uses, needs, relations, results, culture, and complete
  objects are equal candidate directions; the target is the largest effective
  content world followed by actual rooted map nodes. Keep `ca2af9f8` unchanged,
  and do not rerun, tune, stack, or register E35/E36.
  E37 is a separate frozen one-call development regression. It emits only a
  source object, competing content subjects, one selected content world,
  actual map nodes bound to that selected candidate id, and unknowns. Its four
  user-corrected labels remain hidden from model messages. Do not change its
  prompt, cases, repair budget, or acceptance after the live run begins, and do
  not infer production readiness from a development-set pass.
  The frozen E37 run passed contracts but only reached `2/4` for both semantic
  worlds and correctly rooted maps; fact specificity also failed. ADR-017
  rejects map richness as a root judge. Retain deterministic candidate binding
  and rooted parent references only: the Lead must select and freeze the
  content subject before map expansion. Do not rerun, tune, stack, or register
  E37.
  A54 and ADR-018 define the next downstream boundary: semantic recognition
  selects and explains the subject, the content map expands only a frozen root,
  and topic generation turns one rooted map path into an evidence-backed
  premise. Do not make the content map write topics or let topic generation
  reselect the root. A candidate TopicBridge should begin as a thin, optional
  Skill using the existing web search/fetch tools on demand. The model owns
  association and interpretation; primary sources own named works, people,
  history, quotations, numbers, and current facts; the Lead owns final
  convergence. Keep textual observation, interpretation, and creative
  hypothesis distinct, and do not call category, occurrence, narrative trigger,
  or analogy edges market causality. No TopicBridge runtime, vector database,
  GraphRAG index, fixed subagent roster, or core-prompt change is approved
  before the preregistered comparison in ADR-018 passes.
  A55 and ADR-019 reframe semantic recognition, rooted content mapping, and
  topic generation as three inspectable outputs of an open-world marketing
  reading-comprehension core. Validate object meaning, participant/action
  relations, typed map edges, cross-text supporting facts, the central premise,
  and unknown boundaries before optimizing prose. The downstream order is
  `TopicBrief -> MessagePlan -> BaseDraft -> PresentationAdaptation`: first
  decide what is worth saying and make its reasoning coherent, then adapt it to
  oral delivery, short drama, image-text, pure-material, platform, or style.
  Do not let fluent copy hide reading errors, do not implement presentation
  work before the reading layer passes held-out cases, and do not turn
  FrameNet, AMR, STORM, or Project Debater into mandatory runtime dependencies.
- **Format before pushing** — run `make format` (backend) / `pnpm check` (frontend). Backend
  CI enforces `ruff format --check`, so formatting must be clean before a push.
