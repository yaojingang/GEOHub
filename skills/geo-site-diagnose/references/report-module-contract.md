# Report module contract 2

The report format version is `2`. Artifact Bus protocol and Skill manifest contract versions remain `1.0.0`.

| Module | Objective | Chart views | Primary fields |
| --- | --- | ---: | --- |
| GEO conclusion | Establish the weighted readiness profile | 2 | `overall_score`, `confidence`, `dimensions`, `dimension_weights` |
| Access and discovery | Verify crawler access and diagnostic conversion | 2 | `crawler_matrix`, inventory and selected counts, evidence-ready page count |
| Architecture coverage | Verify page families, sample quality, and connections | 3 | page types, `selection.representativeness`, `internal_links` |
| Entity clarity | Compare entity heading and Schema signals | 2 | `entity-heading`, `entity-schema`, `entity_clarity` |
| Answerability | Compare answer readiness with depth and structure | 2 | `answerability`, visible text, headings, lists, tables, FAQ signals |
| Evidence and citability | Compare source, external-link, and numeric proof checks | 2 | `evidence-language`, `external-sources`, `numeric-proof`, `evidence_citation` |
| Authority and trust | Compare accountable-author and contact signals | 2 | `authorship`, `trust-contact`, `authority_trust` |
| Structure and freshness | Inspect Schema, extractability, and update dates | 3 | Schema types, `semantic-landmarks`, `structured-data`, sitemap `lastmod` |
| Page diagnosis | Validate site averages against page-level evidence | 2 | page dimensions, page scores, all nineteen page checks |
| Remediation roadmap | Sequence issues and actions by severity and effort | 3 | page issues, action dimension, severity, impact, effort, priority |

The reproducible ten-page fixture renders 23 chart views. A live report may show fewer rendered charts when evidence is insufficient. Every omitted chart keeps its module slot, displays a concrete gap reason, and preserves the adjacent table. The renderer never turns missing dimensions or page checks into zero.

## Fixed chart vocabulary

- GEO conclusion: marker-free eight-dimension radar and weighted dimension bars
- Access and discovery: crawler access heatmap and true-proportion retention funnel
- Architecture coverage: page-family status bars, representative-page lollipop ranking, and numbered internal-link matrix
- Entity clarity: entity signal heatmap and entity clarity ranking
- Answerability: answerability ranking and content-depth versus structure scatter
- Evidence and citability: citation evidence heatmap and citability ranking
- Authority and trust: trust signal heatmap and authority readiness ranking
- Structure and freshness: Schema treemap, structured-check heatmap, and update-date scatter
- Page diagnosis: page-dimension heatmap and score distribution or small-sample ranking
- Remediation roadmap: issue-severity stacked bars, aggregated circular impact-effort scatter, and remediation ranking

All chart choices follow `report-design-system.md`. A replacement chart must preserve the module question, exact values, evidence table, gap behavior, and the total of 23 chart slots.

## Eligibility rules

- The radar requires all eight numeric dimension scores
- The readiness funnel requires four numeric stage counts. Its retention percentage uses the first valid stage as the denominator and never uses a visual minimum width that distorts the ratio
- The internal-link matrix requires at least two observed nodes and one observed edge
- Page score distribution uses a histogram for three or more observed pages and a ranked-bar fallback for smaller samples
- Schema structure requires at least one observed Schema type
- Freshness distribution requires at least one valid sitemap `lastmod`
- Issue and action views require corresponding issue or action records
- Check matrices encode missing evidence as a separate state outside the numeric score range

## Per-page chapter

Each selected page keeps the selection reason, representativeness, URL, render mode, confidence, score, eight dimension bars, key structural metrics, evidence ID, SHA-256 digest, raw excerpt, observed links, issues, remediation, and all nineteen check records when observed. Source gaps keep their selected page type, URL, failure reason, and empty evidence state without a synthetic score.
