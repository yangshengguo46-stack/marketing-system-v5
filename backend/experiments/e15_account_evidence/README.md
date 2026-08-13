# E15 account evidence experiment

This package is isolated from the active DeerFlow runtime. It tests whether
authorized account videos can become traceable, reviewable structured evidence
without turning the extractor into another incubation decision-maker.

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

This experiment still has no production browser adapter and does not infer true
audience profiles, establish why a post performed, or authorize model training.
Training candidates require separate source rights, atom-level review,
signal-level review and explicit training permission. It is not registered as a
DeerFlow tool or Skill; promotion still requires a real authorized multi-video
account evaluation.

Run its focused coverage from `backend/`:

```bash
PYTHONPATH=. uv run pytest tests/experiments -q
```
