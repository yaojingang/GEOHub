# Data Governance

GEOHub classifies run artifacts by retention class and keeps operational aggregation metadata-only.

| Class | Default retention | Intended scope |
|---|---:|---|
| L0 | 365 days | Public, synthetic, or aggregate metadata |
| L1 | 180 days | Approved internal operational records |
| L2 | 30 days | Ordinary run artifacts and replayable inputs |
| L3 | 7 days | Sensitive, short-lived run artifacts |

Each run defaults to L2. An optional `retention-policy.json` may contain one exact field, `data_class`, with `L0`, `L1`, `L2`, or `L3`. The policy applies only to `run-*` directories inside the explicitly supplied runs root. Original customer inputs outside a run remain outside this subsystem.

## Safe lifecycle

1. Preview expired targets with `geo-seo-hub data-retention --runs-root <root> --apply-policy`.
2. Add `--confirm` to atomically move targets into `.geohub-trash/<batch-id>/runs/` on the same filesystem.
3. Recover with `--recover-batch <batch-id>` during the seven-day grace period.
4. Purge with `--purge-batch <batch-id> --confirm` after the grace period.

Broad roots, repository roots, home directories, symlinked runs, malformed manifests, cross-filesystem moves, collisions, and platforms without symlink-safe recursive deletion fail closed. A recover manifest records relative run IDs and a movement timestamp. Permanent purge is the only irreversible stage.

## Observability boundary

`run-lineage.json` records stable trace and span IDs, Skill ID, artifact SHA-256 hashes, metric names, status, duration, token count, cost, error class, and data class. It excludes prompts, response bodies, customer names, source URIs, and absolute paths. `scripts/aggregate_adoption_drift.py` reads valid lineage records and emits only counters plus validation gaps.
