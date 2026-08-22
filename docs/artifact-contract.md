# Artifact Contract

Every execution writes into a newly allocated run directory beneath the user-selected runs root. Publication is atomic. Inputs are snapshotted where replay is supported, generated artifacts carry protocol `1.0.0`, and `run-manifest.json` records the contract. JSON writers emit standard JSON with non-finite numbers forbidden; ranking validates every weighted intermediate and result before publication.

Executable runs publish `run-lineage.json` with metadata-only trace data and SHA-256 artifact hashes. TaskPlan protocol `1.0.0` records the immutable execution graph and semantic digest. Resumable orchestration uses `workflow-state.json` version `2.0.0` with a bound plan digest, required-input digests, per-node idempotency keys, retry budgets, checkpoint checksums, explicit approval, external publication and observation evidence states, and bounded relative artifact references. Required inputs and resumed external evidence are rechecked against their recorded SHA-256 values. Migration from workflow state `1.0.0` writes a sibling backup before replacement. Workflow state never changes an already published run directory.

Evidence states remain explicit: provided, observed, inferred, unverified, source gap, or blocked by evidence. Missing source material cannot become a citation. Optional DOCX/PDF render failures do not invalidate core JSON, Markdown, HTML, evidence, quality, and manifest artifacts. In that case, `run-manifest.json` records `degraded: true`, exact `missing_dependencies`, and separate `renderer_errors`. A successful fallback remains degraded when its preferred renderer dependency is missing or fails.

Strategy runs add bounded candidates, fidelity, experiment, publication-handoff, and memory artifacts. Memory begins empty and accepts only positive measured observations that pass fidelity. Knowledge runs add normalized entities, facts, source-lined relations, communities, conflicts, coverage, query results, and evidence gaps. Conflicting values remain available for review.

Release evidence lives outside run directories. The SBOM records build-environment dependency identities. Local provenance binds the staged source digest, commit revision, SBOM digest, and eleven archive digests while declaring an unsigned local builder. Production Readiness separates deterministic passes from missing external evidence.

Rollback removes the specific run directory. Code rollback keeps executor, schema, registry, manifest, and wrapper changes together.
