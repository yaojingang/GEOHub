---
name: geo-diagnose
description: Diagnose a brand, website, or page for evidence-backed GEO gaps and opportunities from user-supplied URLs, HTML, or evidence. Use for brand diagnosis, website or page audits, GEO gap analysis, and 品牌诊断、网站诊断、页面诊断. Excludes live AI-platform recall, ranking, and citation-share measurement.
---

# GEO Diagnose

## Workflow

1. Read `references/diagnosis-method.md`; read `references/audit-catalog.md` for non-legacy audit execution.
2. Prepare the diagnosis brief contract.
3. Run `python3 scripts/run_diagnose.py --input <brief.json> --output <runs-root> --execution-mode <legacy|deterministic|research|provider>`. Legacy remains the compatibility default.
4. Inspect `quality-report.json`, `run-lineage.json`, `source_status`, audit components, and limitations before using findings.
5. Deliver the complete Artifact Bus run directory.

## Output contract

Return `<runs-root>/<run-id>/` containing the normalized input and replayable HTML snapshots under `input/sources/`, structured diagnosis, deterministic Markdown report, evidence-linked remediation query map, opportunity map, quality report, run lineage, and run manifest. Non-legacy diagnosis adds versioned audit results, reconstructable score components, execution status, and a semantic digest to `diagnosis.json`.

## Boundaries

Fetch only explicit public HTTP(S) canonical URLs without query strings. Accept remote HTML/XHTML only and keep unavailable or unsupported sources as `source_gap`. Every observed, provided, or inferred finding carries a content-derived evidence ID. Provider audit mode has no packaged adapter and records a degraded deterministic fallback. Never claim live AI-platform recall, ranking, or citation share.
