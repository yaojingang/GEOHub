# Artifact Contract

Every execution writes into a newly allocated run directory beneath the user-selected runs root. Publication is atomic. Inputs are snapshotted where replay is supported, generated artifacts carry protocol `1.0.0`, and `run-manifest.json` records the contract. JSON writers emit standard JSON with non-finite numbers forbidden; ranking validates every weighted intermediate and result before publication.

Evidence states remain explicit: provided, observed, inferred, unverified, source gap, or blocked by evidence. Missing source material cannot become a citation. Optional DOCX/PDF render failures do not invalidate core JSON, Markdown, HTML, evidence, quality, and manifest artifacts. In that case, `run-manifest.json` records `degraded: true`, exact `missing_dependencies`, and separate `renderer_errors`. A successful fallback remains degraded when its preferred renderer dependency is missing or fails.

Research-grounded runs add `research-context.json` without changing Artifact Bus protocol `1.0.0`. Diagnose publishes `diagnosis-funnel.json`; Content publishes `content-evidence-units.json`; Measure publishes `measurement-report.json`. Measurement preserves total, eligible, answered, missing, and excluded counts, plus explicit numerators, denominators, Wilson intervals, platform strata, observation source URIs, and `causal_status: descriptive`.

Rollback removes the specific run directory. Code rollback keeps executor, schema, registry, manifest, and wrapper changes together.
