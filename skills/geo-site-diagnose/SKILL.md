---
name: geo-site-diagnose
description: Crawl one public website from a supplied URL, select up to ten representative page types, score evidence-lined GEO readiness, and generate a standalone visual HTML report. Use for 网站 GEO 诊断、全站 GEO 体检、网站 GEO 审计, or requests such as “帮我诊断网站GEO并附上网址”. Excludes single-page or brand-only diagnosis, live AI ranking or citation measurement, authenticated sites, and website modification.
---

# GEOHub Website Diagnosis

## Workflow

1. Read `references/site-diagnosis-method.md`, `references/crawler-policy.md`, and `references/scoring-policy.md`.
2. Extract the single public URL. Ask only for the URL when it is missing.
3. Run `python3 scripts/run_site_diagnose.py --url <URL> --output <runs-root> --locale <locale> --max-pages 10 --render auto`.
4. Inspect `quality-report.json`, diagnostic confidence, source gaps, and limitations before presenting scores.
5. Validate the report against `references/report-module-contract.md` and `references/report-design-system.md`.
6. Deliver the complete Artifact Bus run directory and open `report.html` for the user.

## Output contract

Return a bounded run containing source snapshots, crawl and sampling manifests, structured site and page diagnoses, evidence ledger, remediation backlog, quality and lineage artifacts, and one offline `report.html`. Read `references/report-contract.md` for the file contract and report format boundary.

## Boundaries

Fetch only public HTTP(S) resources on the approved canonical host. Discovery is bounded to 500 inventory URLs, five sitemaps, ten representative pages, 15 MB, and 90 seconds. Preserve blocked or unavailable pages as `source_gap`. Scores describe observed readiness signals and never claim live AI ranking, recall, citations, traffic, or business effects.
