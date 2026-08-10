---
name: geo-content
description: Create evidence-lined GEO titles, explainers, neutral comparisons, method-backed rankings, page blueprints, refinements, and article-friendly Markdown. Use for title generation, 科普/解释、对比、榜单、页面蓝图、内容优化, and article-friendly rewriting. Excludes unsupported factual claims, winner declarations without like-for-like evidence, network research, publishing, and live ranking measurement.
---

# GEO Content

## Workflow

1. Read `references/content-method.md`, then select one mode from `references/modes.md`.
2. Prepare a strict content brief using `references/input-example.json` and `references/evidence-policy.md`.
3. Run the deterministic `python3 scripts/run_content.py --input <brief.json> --output <runs-root>` wrapper or `python -m geo_seo_hub content --input <brief.json> --output <runs-root>`.
4. Inspect `content-evidence-units.json`, `research-context.json`, `quality-report.json`, `evidence-ledger.json`, content status, and supplement requests.
5. Deliver the complete run described by `references/output-contract.md`.

## Boundaries

Run offline. Treat only supplied evidence as factual. Classify every evidence, preserved-source, research-method, operational-guidance, and evidence-gap unit with explicit lineage. Keep research methods conditional and free of effect guarantees. Render HTML locally with escaped text and no external assets. Optional DOCX/PDF failures degrade explicitly while core artifacts remain usable.
