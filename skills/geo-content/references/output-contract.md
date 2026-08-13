# Output contract

Every successful request publishes `<runs-root>/<run-id>/` with normalized `input/content-brief.json`, optional `input/source.md`, `content-spec.json`, `content.json`, `content-evidence-units.json`, `content.md`, `content.html`, `evidence-ledger.json`, `research-context.json`, `quality-report.json`, and `run-manifest.json`.

All runs include `run-lineage.json`. Non-legacy execution also includes `claim-map.json` and `content-pipeline.json`. Ranking MCDA remains nested in `content.json` so the raw matrix, normalized matrix, weights, results, and sensitivity stay beside the ranking decision.

The manifest excludes itself and lists every real staged artifact. Requested DOCX/PDF files appear only after successful rendering. Missing dependencies or renderer failures leave core output intact and add an explicit quality warning plus `completed-with-warnings` manifest status.
