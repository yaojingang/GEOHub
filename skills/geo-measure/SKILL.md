---
name: geo-measure
description: Aggregate explicit GEO or AI-search observation records into transparent rates, denominators, missing-answer counts, platform strata, and intervals. Use for citation measurement, AI visibility tracking, repeated observation analysis, and 引用监测、AI 可见度衡量、效果测量. Requires supplied observations and excludes live platform collection, account access, causal attribution, ranking guarantees, and continuous monitoring.
---

# GEO Measure

## Workflow

1. Read `references/measurement-method.md` and prepare a strict measurement brief.
2. Run `python3 scripts/run_measure.py --input <brief.json> --output <runs-root>` or `python -m geo_seo_hub measure --input <brief.json> --output <runs-root>`.
3. Inspect `measurement-report.json`, `research-context.json`, `evidence-ledger.json`, and `quality-report.json` together.
4. Report the declared platform scope, collection window, eligible trials, missing answers, exclusions, numerators, denominators, intervals, and limitations.

## Output contract

Return `<runs-root>/<run-id>/` with the normalized brief, structured measurement report, Markdown summary, observation lineage, research context, quality report, and run manifest.

## Boundaries

Operate offline on explicit observation records. Keep eligible unanswered trials in unconditional denominators. Treat all v0.3 results as descriptive, including briefs that declare an intervention and comparator. Never collect platform data, infer missing responses, convert readiness proxies into outcomes, or promise citation, ranking, traffic, revenue, or future platform effects.
