---
name: geo-diagnose
description: Diagnose a brand, website, or page for evidence-backed GEO gaps and opportunities from user-supplied URLs, HTML, or evidence. Use for brand diagnosis, website or page audits, GEO gap analysis, and 品牌诊断、网站诊断、页面诊断. Excludes live AI-platform recall, ranking, and citation-share measurement.
---

# GEO Diagnose

## Workflow

1. Read `references/diagnosis-method.md` and prepare the diagnosis brief contract.
2. Run the deterministic `python3 scripts/run_diagnose.py --input <brief.json> --output <runs-root>` wrapper or `python -m geo_seo_hub diagnose --input <brief.json> --output <runs-root>`.
3. Inspect `quality-report.json`, `source_status`, and `limitations` before using findings.
4. Deliver the complete Artifact Bus run directory.

## Output contract

Return `<runs-root>/<run-id>/` containing the normalized input and replayable HTML snapshots under `input/sources/`, structured diagnosis, deterministic Markdown report, evidence-linked remediation query map, opportunity map, quality report, and run manifest.

## Boundaries

Fetch only explicit public HTTP(S) canonical URLs without query strings. Accept remote HTML/XHTML only and keep unavailable or unsupported sources as `source_gap`. Every observed, provided, or inferred finding carries a content-derived evidence ID. Never claim live AI-platform recall, ranking, or citation share.
