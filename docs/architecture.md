# Architecture

GEO SEO Hub separates control, intelligence, quality, and trust responsibilities. The current runtime is GEO-first; the shared evidence, query, content, schema, lineage, and Artifact Bus layers form the compatibility boundary for future SEO capabilities.

1. `registry/skills.yaml` declares active and planned capabilities.
2. `geo_seo_hub.router` emits an explicit decision object for one Skill, one exact workflow, clarification, abstention, or unavailable capability. Lexical matching is the always-on baseline; a prepared local FastEmbed cache may add bounded clause-level semantic evidence.
3. `geo_seo_hub.control.planning` compiles executable decisions into deterministic TaskPlans with typed bindings, permission profiles, retry limits, idempotency metadata, and digests.
4. `geo_seo_hub.control.workflow` persists workflow state `2.0.0` for required-input digests, checkpoints, bounded retries, abort, approval, publication receipt, and observation evidence. Version `1.0.0` state requires an explicit backup migration.
5. `geo_seo_hub.control.execution` serializes execution per state file, revalidates input/output boundaries and artifact digests, enforces process lifetime and output limits, and runs active local executors until completion or the next gate.
6. Domain intelligence modules implement discovery, audit, content, measurement, optimization, and knowledge governance behind public compatibility façades.
7. Active executors validate file-backed inputs and publish protocol `1.0.0` runs through the Artifact Bus.
8. JSON Schemas, lineage, evaluation, observability, retention, trust, SBOM, provenance, and readiness reports preserve evidence and promotion boundaries.

`geo-discover`, `geo-content`, `geo-measure`, `geo-strategy`, and `geo-knowledge` are offline. `geo-diagnose` supports replay snapshots and a tightly bounded explicit-source network mode. `geo-publish` has a null entrypoint and cannot execute. `strategy-observation-loop` moves through an approval node and two schema-validated external evidence nodes; it never performs publication or platform collection.

Dedicated SEO providers are not registered in version 0.6.0. Future SEO additions must use distinct Registry entries and preserve the same evidence, permission, output, and degradation contracts before they become runnable. Architecture decisions are recorded under `docs/decisions/`.
