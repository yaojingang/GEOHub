---
name: geo-measure
description: Measure GEO visibility from an approved, file-backed engine observation bundle. Use for AI answer mention rate, source inclusion, citation share, query-panel coverage, GEO monitoring, 监测 AI 可见度, 衡量 GEO 效果, and offline baseline comparison. Exclude live scraping, platform login, automated collection, and unsupported causal claims.
---

# GEO Measure

## Workflow

1. Read `references/measurement-method.md` and verify collection permission.
2. Prepare a protocol `1.0.0` engine observation bundle from manual export, approved API, or recorded fixture.
3. Run `python3 scripts/run_measure.py --input <bundle.json> --output <runs-root>`.
4. Inspect `visibility-report.json`, `quality-report.json`, and `run-lineage.json`; surface every gap and collection limitation.
5. Deliver the Artifact Bus run directory as the output contract.

## Output contract

Produce the input snapshot, `visibility-report.json`, `quality-report.json`, `run-lineage.json`, and `run-manifest.json`. Preserve query-level components, per-engine metrics, numerators, denominators, missing counts, panel version, and semantic digest.

## Boundaries

Measurement is offline and file-backed. It never logs in, scrapes consumer AI pages, bypasses access controls, or turns recorded fixtures into live-effect evidence. Read `references/output-contract.md` before making a comparison claim.
