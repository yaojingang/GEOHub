---
name: geo-content
description: Create evidence-lined GEO titles, explainers, neutral comparisons, method-backed rankings, page blueprints, refinements, and article-friendly Markdown. Use for title generation, 科普/解释、对比、榜单、页面蓝图、内容优化, and article-friendly rewriting. Excludes unsupported factual claims, winner declarations without like-for-like evidence, network research, publishing, and live ranking measurement.
---

# GEO Content

## Workflow

1. Read `references/content-method.md`, then select one mode from `references/modes.md`. Read `references/content-pipeline-v2.md` for non-legacy execution and `references/mcda-policy.md` for ranking.
2. Prepare a strict content brief using `references/input-example.json` and `references/evidence-policy.md`.
3. Run `python3 scripts/run_content.py --input <brief.json> --output <runs-root> --execution-mode <legacy|deterministic|research|provider>`. Legacy remains the compatibility default.
4. Inspect `quality-report.json`, `run-lineage.json`, `evidence-ledger.json`, claim map when present, content status, and supplement requests.
5. Deliver the complete run described by `references/output-contract.md`.

## Boundaries

Run offline. Treat only supplied evidence as factual. Keep unsupported material as guidance, `unverified`, `source_gap`, or `blocked-by-evidence`. Provider mode has no packaged drafting adapter and records a degraded deterministic fallback. Render HTML locally with escaped text and no external assets. Optional DOCX/PDF failures degrade explicitly while core artifacts remain usable.
