# E15 account evidence experiment

This package is isolated from the active DeerFlow runtime. It tests whether
authorized account videos can become traceable, reviewable structured evidence
without turning the extractor into another incubation decision-maker.

This experiment is frozen after the single-video technical validation. The
product's 80-point target applies to the marketing brain, not video
understanding; do not extend this package merely to improve media interpretation.

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

This experiment does not collect a platform account, infer true audience
profiles, establish why a post performed, or authorize model training. Training
candidates require separate source rights, atom-level review, signal-level
review and explicit training permission. It is not registered as a DeerFlow
tool or Skill; promotion still requires a real authorized multi-video account
evaluation.
