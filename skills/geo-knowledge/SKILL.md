---
name: geo-knowledge
description: Build and query an evidence-lined GEO knowledge graph from approved source bundles. Use for entity normalization, relation lineage, conflicting fact preservation, incremental source-hash updates, local/global knowledge queries, 知识图谱, 知识库, and 知识治理. Exclude unsourced facts, hidden conflict resolution, autonomous crawling, and external database mutation.
---

# GEO Knowledge

## Workflow

1. Read `references/knowledge-method.md` and prepare approved source bundles with stable IDs and SHA-256 hashes.
2. Run `python3 scripts/run_knowledge.py --input <request.json> --output <runs-root>`.
3. Inspect canonical identities, aliases, relation source IDs, validity dates, source coverage, conflicts, and gaps.
4. Use the local query for an entity neighborhood or the global query for communities, coverage, conflicts, and gaps.
5. For incremental updates, replace only source bundles whose hashes changed and rebuild the governed graph.

## Output contract

Produce the input snapshot, `knowledge-graph.json`, query result, evidence ledger, quality report, lineage, and manifest. Read `references/output-contract.md` before reuse.

## Boundaries

Execution stays offline and file-backed. Conflicting approved facts remain visible for human review. The Skill never crawls, logs in, mutates an external knowledge base, or silently selects one conflicting value.
