# E15 account evidence experiment

This package is isolated from the active DeerFlow runtime. It tests whether
platform search and account videos can become traceable, reviewable structured
evidence without turning the extractor into another incubation decision-maker.

This experiment passed a single-video technical validation. The product's
80-point target applies to the marketing brain, not video understanding; do not
extend this package merely to improve media interpretation.

## Account-link boundary

The package also contains a pre-runtime boundary for a future user-supplied
account link:

```text
user-supplied URL + rights + sample cap
-> local visible-browser or first-party collector
-> strict AccountSourceSnapshot
-> content-addressed local cache
-> selected stable media artifacts
-> AccountEvidencePack
-> bounded LeadAccountProjection
```

`account_link_collection.py` is a collector port, not a crawler. A call may
request at most 24 posts, and the collector can return only whitelisted public
profile and post observations. Raw HTML/DOM, Cookie or LocalStorage values,
temporary media URLs, and browser internals fail schema validation.

That output rule does not prohibit the local connector from reading an
account's Cookie or StorageState. `local_browser_credentials.py` registers
account-scoped local browser state, can read an already-running local Chrome
over CDP, and passes the filtered state directly into Playwright. Credential
values stay in the connector process and untracked local state files; search
results, Lead projections, logs, tests, and the registry index contain no
credential values.

## Cross-platform search boundary

`platform_search.py` defines one strict contract for Douyin, Xiaohongshu,
WeChat Channels, Kuaishou, Bilibili, and TikTok. It keeps keyword content
search, keyword account search, and bounded account post-list collection as
three distinct operations.

`platform_search_adapters.py` contains clean-room local Playwright adapters for
the five web platforms and a desktop bridge port for WeChat Channels. The web
runner captures structured JSON responses in memory and falls back to visible
canonical links. It never writes full responses, HTML, screenshots, or browser
state to an evidence result. One platform failure is isolated from the others,
and an unrecognized empty page returns `partial` or `schema_drift` rather than
claiming that the platform has no results.

As of 2026-08-13, Bilibili public keyword content and account search passed
live smoke checks. Douyin passed one real third-party account-link acceptance
with local login state, author-qualified recent posts, and bounded media and
audience evidence. Xiaohongshu, Kuaishou, and TikTok have implementation
coverage but still require real local login-state acceptance. WeChat Channels
has the strict desktop bridge contract but no accepted desktop search bridge.
None of these adapters is registered as a Lead tool or MCP server.

## Audience-intelligence boundary

This capability is **audience-intelligence collection**, not comment
collection. Comments are one visible interaction source. The contract covers
account scale, growth history, follower demographics, audience interests,
audience activity, content interactions, live audience, and commerce affinity.
Every requested dataset has a separate coverage receipt, so an unavailable
demographic or live field cannot be silently inferred from comments.

`audience_snapshot_adapter.py` can already turn public profile scale and sampled
post response into observed metrics. `audience_ledger.py` appends
content-addressed snapshots and deterministically derives change across time.
Observed platform values, local derivations, third-party estimates, and model
estimates use different provenance contracts.

Actor-linked interactions are pseudonymized before they enter a snapshot.
`douyin_audience_adapter.py` is the first detailed collector accepted in this
isolated package. It only opens canonical posts present in the bound account
snapshot, triggers the visible first-party response, and converts raw actor IDs
to stable local pseudonyms before persistence. The result remains a bounded
response sample, not a follower census or demographic profile.
`hllm_audience.py` then adapts only genuine audience behavior sequences to the
pinned ByteDance HLLM-Creator row/request shape. It rejects creator publishing
history and aggregate account performance as audience substitutes. The adapter
does not bundle weights and a generic LLM cannot issue its checkpoint receipt;
real HLLM inference remains pending on a compatible model service.

`source_snapshot.py` persists the whitelisted observations by canonical SHA-256,
so repeated identical captures reuse one local snapshot. `lead_projection.py`
does not send that whole snapshot or the full evidence pack to the Lead. It
keeps a bounded set of candidate patterns, representative post and evidence
IDs, coverage, limitations, and source hashes under a hard UTF-8 byte budget
(16 KB by default). Account identity, rights, and analyzed post IDs must match
before projection. Profile text and captions remain untrusted evidence and can
never act as instructions.

Example from `backend/`:

```bash
uv run python -m experiments.e15_account_evidence.cli \
  --account-ref account://authorized/example \
  --video post-001=/absolute/path/to/video.mp4 \
  --output-dir ../.deer-flow/e15-account-evidence/example-run \
  --model doubao-seed-evolving \
  --source-rights user_owned \
  --rights-ref rights://project/example \
  --cloud-capability asr \
  --cloud-capability ocr \
  --cloud-capability scene_segmentation \
  --allow-cloud-processing
```

The output directory is created atomically and contains:

- `account-evidence-pack.json`: media atoms, bounded semantic signals and
  deterministic cross-video aggregation;
- `signal-review-queue.json`: every model signal starts as `pending` and must
  be accepted, corrected, rejected or contested by a reviewer;
- `evidence-review-queue.json`: every ASR, OCR or scene atom starts as
  `pending`, so recognition errors can be rejected before they become labels;
- `manifest.json`: model, capability, source-rights, consent and content
  hashes.

The extractor separates `observed`, `inferred` and `unknown` signals. Unknowns
remain in the per-video record but never become account-level patterns. The
deterministic aggregator reports support and sample coverage; it does not infer
why a post performed. Both review queues must be complete, the pack hash must
still match, and model-training permission must be explicit before code can
build a training candidate.

This experiment still has no production browser/MCP registration and has not
accepted detailed collectors for the other platforms or real HLLM inference. It does
not establish why a post performed or authorize model training. Training candidates require separate source rights, atom-level
review, signal-level review and explicit training permission. Promotion still
requires platform-by-platform real account acceptance and a real multi-video
account evaluation.

Run its focused coverage from `backend/`:

```bash
PYTHONPATH=. uv run pytest tests/experiments -q
```
