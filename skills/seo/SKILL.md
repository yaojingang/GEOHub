---
name: seo
description: Turn one natural-language request into an evidence-bounded SEO work plan across technical SEO, crawling and indexing, Search Console incidents, keyword-to-page mapping, migrations, experiments, international or ecommerce SEO, and AI-search foundations. Use for 一句话SEO、技术SEO、自然搜索、收录诊断、关键词页面映射 and website SEO. Exclude paid search, ASO, ranking guarantees, link spam, live mutation without authorization, and unsupported metrics.
---

# GEO SEO Hub — One-line SEO

## Workflow

1. Read `references/seo-method.md` and normalize the request into `references/input-example.json` shape.
2. Run `python3 scripts/run_seo.py --input <brief.json> --output <runs-root>` or `python -m geo_seo_hub seo --input <brief.json> --output <runs-root>`.
3. Use the selected work mode and action plan to collect the named evidence. Preserve the coverage ledger and rerun inputs.
4. State observations, inference, hypotheses, and missing evidence separately. The deterministic planner keeps `findings` empty; later analysis needs a separately validated evidence-backed contract.
5. Keep audit and planning read-only. Implement only when the user explicitly authorizes the target, change, verification, and rollback boundary.

## Output contract

Return the normalized brief, `seo-plan.json`, a Markdown report, evidence ledger, quality report, and run manifest under one Artifact Bus run.

## Boundaries

Never invent search volume, difficulty, rankings, traffic, backlinks, crawl, index, competitor, conversion, or citation metrics. Keep provider and surface rules separate. Crawling, indexing, ranking, rich results, traffic, revenue, and AI citations remain unguaranteed outcomes.
