# Migration to 0.5.0

## Stable surfaces

- Distribution and CLI: `geo-seo-hub`
- Python package: `geo_seo_hub`
- Installed data root: `share/geo-seo-hub`
- Existing commands: `route`, `discover`, `diagnose`, `content`, `measure`, `eval`, and `data-retention`
- Artifact protocol: `1.0.0`
- Existing public imports and legacy default execution paths

## Additive surfaces

- Commands: `strategy` and `knowledge`
- Active Skills: `geo-strategy` and `geo-knowledge`
- Optional execution modes: `deterministic`, `research`, and `provider` for discovery, diagnosis, and content
- Artifact sidecars: `run-lineage.json`, claim map, pipeline reports, strategy memory, publication handoff, knowledge graph, and workflow state
- Release evidence: SBOM, local provenance, provenance verification, and Production Readiness Review

## Upgrade procedure

Create a fresh environment, install 0.5.0, run `geo-seo-hub --version`, execute the legacy fixture smokes, then test the two new commands with the supplied fixtures. Package consumers should expect eleven archives and seven active provider entries.

## Rollback

Set `geo-strategy` and `geo-knowledge` to `planned`, remove their CLI and data-file entries, restore the prior package matrix, and retain protocol `1.0.0` run artifacts. Discovery, diagnosis, and content can use `--execution-mode legacy`. Lineage sidecars remain readable and can be ignored by older consumers that allow additive files.

Generated 0.5.0 runs should remain available for audit. A rollback never rewrites a published run directory.
