# Evaluation Policy

The 0.3.0 local gate uses 373 Chinese/English router cases, 33 per-Skill trigger cases, and 25 deterministic output cases across five active Skills. Router precision must be at least `0.97`, recall at least `0.93`, trigger and output contract compliance exactly `100%`, and fabricated citations exactly `0`.

An exact skill/workflow/runnable match counts as a true positive. Every mismatch contributes one false positive and one false negative. Output cases use synthetic, file-backed fixtures without network services or real customer data.

Recorded fixtures and deterministic command runs are reproducibility evidence. Provider-backed model evidence, real-platform benchmarks, and human blind review remain `missing evidence` until independently collected. Pending blind pairs do not enter agreement metrics.

Run the external local integration with `python3 scripts/run_yao_meta_gates.py --meta-root ../yao-meta-skill`. The wrapper parses each generated JSON report in addition to checking the command exit code. Review Studio warnings are mapped one by one to deterministic repository evidence or an unexpired entry in `reports/review-waivers.json`. Unknown, duplicate, stale, expired, or unclassified warnings are release-blocking.

CI has no machine-local meta checkout and runs `python3 scripts/run_yao_meta_gates.py --verify-existing`. That check validates the gate-report schema and digest, every structured report status and digest, the current source digest, waiver schema and expiry, warning counts, and portable public paths. The waiver ledger must exactly match 13 approved `(skill_id, gate)` pairs across five active Skills and three suite-level external-evidence gaps; empty, unknown, missing, or semantically duplicated entries fail the gate. `pass-with-waivers` keeps missing external evidence separate from deterministic passes.
