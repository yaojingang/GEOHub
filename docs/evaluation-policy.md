# Evaluation Policy

The local gate uses at least 60 Chinese/English router cases and 35 deterministic output cases. Router precision must be at least `0.97`, recall at least `0.93`, output contract compliance exactly `100%`, and fabricated citations exactly `0`.

An exact skill/workflow/runnable match counts as a true positive. Every mismatch contributes one false positive and one false negative. Output cases use synthetic, file-backed fixtures without network services or real customer data.

Recorded fixtures and deterministic command runs are reproducibility evidence. Provider-backed model evidence, real-platform benchmarks, and human blind review remain `missing evidence` until independently collected. Pending blind pairs do not enter agreement metrics.

## Output Eval Lab

`geo-seo-hub eval` runs versioned tasks through deterministic recorded fixtures, an explicit command runner, or the OpenAI provider runner. Every result distinguishes `recorded_fixture`, `command`, and `model`; a run can use `model` only when provider and model metadata are present. The lab writes `eval-result.json`, a randomized `blind-review-pack.json`, and a separately stored `blind-answer-key.json`.

Command mode accepts a JSON string list and never invokes a shell. It requires distinct baseline and candidate wheel files, installs them into separate temporary targets, proves each import came from its own target, and records both SHA-256 digests. The `{python}` token selects the corresponding isolated Python runner. Provider mode fails closed when `OPENAI_API_KEY`, `GEOHUB_GENERATOR_MODEL_A`, or `GEOHUB_GENERATOR_MODEL_B` is absent. Credentials never enter artifacts.

Provider execution snapshots every declared UTF-8 input file into the runner request, applies task-level input/output limits, caps the combined suite at 25 cases, and performs a conservative cost preflight. The default maximum is `$25` through `GEOHUB_MAX_EVAL_COST_USD`; a higher value also requires `GEOHUB_EVAL_BUDGET_APPROVAL`. Each configured model requires explicit input/output prices so recorded costs remain auditable.

Private holdouts stay local by default. Provider transmission requires `GEOHUB_PRIVATE_PROVIDER_CONSENT=1`, a non-empty `GEOHUB_PRIVATE_DATA_CLASSIFICATION`, and `GEOHUB_PRIVATE_APPROVED_PROVIDER=openai`. Reports retain a consent digest and redact private task material.

The public quality-lab suite contains versioned tasks and blind pairs spanning routing, discovery, diagnosis, content, and adversarial evidence boundaries. The repository output gate additionally covers measurement, strategy, and knowledge. Private holdout evidence stays outside Git and distribution archives through `GEOHUB_PRIVATE_EVAL_ROOT`. Human decisions require reviewer identity, review time, winner, confidence, and rubric reason. Pending or malformed decisions never count toward agreement.

Run the external local integration with `python3 scripts/run_yao_meta_gates.py --meta-root ../yao-meta-skill`. The wrapper parses each generated JSON report in addition to checking the command exit code. Review Studio warnings are mapped one by one to deterministic repository evidence or an unexpired entry in `reports/review-waivers.json`. Unknown, duplicate, stale, expired, or unclassified warnings are release-blocking.

CI has no machine-local meta checkout and runs `python3 scripts/run_yao_meta_gates.py --verify-existing`. That check validates the gate-report schema and digest, every structured report status and digest, the current source digest, waiver schema and expiry, warning counts, and portable public paths. The waiver ledger must exactly match the approved 17 `(skill_id, gate)` pairs; empty, unknown, missing, or semantically duplicated entries fail the gate. `pass-with-waivers` keeps missing external evidence separate from deterministic passes.
