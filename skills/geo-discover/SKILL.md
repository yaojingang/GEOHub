---
name: geo-discover
description: Discover evidence-aware GEO questions, query rewrites, intent clusters, and prioritized content opportunities from a structured brief. Use for AI search intent mining, question or keyword expansion, query research, FAQ discovery, 拓词, and GEO topic discovery in Chinese or English.
---

# GEO Discover

## Workflow

1. Read 'references/discovery-method.md' and prepare a protocol '1.0.0' GEO brief.
2. Run the deterministic `python3 scripts/run_discover.py --input <brief.json> --output <runs-root>` wrapper or `python -m geo_seo_hub discover --input <brief.json> --output <runs-root>`.
3. Inspect 'research-context.json' and 'quality-report.json'; surface the source scope, limitations, warnings, and failed checks.
4. Deliver the Artifact Bus directory as the output contract.

## Output contract

Treat the output argument as the runs root. Produce '<runs-root>/<run-id>/input/geo-brief.json', 'run-manifest.json', 'evidence-ledger.json', 'query-map.json', 'opportunity-map.json', 'research-context.json', and 'quality-report.json'. Return the actual '<runs-root>/<run-id>' directory.

## Boundaries

Discovery is deterministic and file-backed. It normalizes and deduplicates query dimensions, records missing evidence, and treats query diversity as a conditional planning hypothesis. It never invents platform responses, volume, difficulty, ranking, conversion, competitor, or customer data. Diagnosis and content generation remain separate registry stages.
