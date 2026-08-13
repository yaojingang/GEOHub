---
name: geo-discover
description: Discover evidence-aware GEO questions, query rewrites, intent clusters, and prioritized content opportunities from a structured brief. Use for AI search intent mining, question or keyword expansion, query research, FAQ discovery, 拓词, and GEO topic discovery in Chinese or English.
---

# GEO Discover

## Workflow

1. Read `references/discovery-method.md`; read `references/discovery-method-v2.md` when requesting a non-legacy execution mode.
2. Prepare a protocol `1.0.0` file-backed GEO brief.
3. Run `python3 scripts/run_discover.py --input <brief.json> --output <runs-root> --execution-mode <legacy|deterministic|research|provider>`. Legacy remains the compatibility default.
4. Inspect `quality-report.json` and `run-lineage.json`; surface all warnings and failed checks.
5. Deliver the Artifact Bus directory as the output contract.

## Output contract

Treat the output argument as the runs root. Produce `<runs-root>/<run-id>/input/geo-brief.json`, `run-manifest.json`, `run-lineage.json`, `evidence-ledger.json`, `query-map.json`, `opportunity-map.json`, and `quality-report.json`. Return the actual `<runs-root>/<run-id>` directory.

## Boundaries

Legacy and deterministic modes are offline and file-backed. Research mode consumes only approved evidence already present in the brief. Provider mode needs an explicit runtime adapter; the packaged CLI has no adapter and degrades to deterministic generation with a recorded failure. Discovery records missing evidence and never invents platform responses, volume, ranking, conversion, competitor, or customer data. Diagnosis and content generation remain separate Registry stages.
