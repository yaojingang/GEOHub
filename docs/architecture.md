# Architecture

GEO SEO Hub separates control, intelligence, quality, and trust responsibilities. The current runtime is GEO-first; the shared evidence, query, content, schema, lineage, and Artifact Bus layers form the compatibility boundary for future SEO capabilities.

1. `registry/skills.yaml` declares active and planned capabilities.
2. `geo_seo_hub.router` resolves one smallest Skill or one exact stable workflow DAG under `skills/RESOLVER.md`. Its lexical result remains the production decision. A semantic adapter may add a scored shadow assessment without gaining execution authority.
3. `geo_seo_hub.control.workflow` persists strict workflow state for checkpoint, resume, retry, abort, approval, publication wait, and observation wait boundaries.
4. Domain intelligence modules implement discovery, audit, content, measurement, optimization, and knowledge governance behind public compatibility façades.
5. Active executors validate file-backed inputs and publish protocol `1.0.0` runs through the Artifact Bus.
6. JSON Schemas, lineage, evaluation, observability, retention, trust, SBOM, provenance, and readiness reports preserve evidence and promotion boundaries.

`geo-discover`, `geo-content`, `geo-measure`, `geo-strategy`, and `geo-knowledge` are offline. `geo-diagnose` supports replay snapshots and a tightly bounded explicit-source network mode. `geo-publish` has a null entrypoint and cannot execute. Strategy publication and post-publication observation remain explicit external workflow states.

Dedicated SEO providers are not registered in version 0.5.0. Future SEO additions must use distinct Registry entries and preserve the same evidence, permission, output, and degradation contracts before they become runnable. Architecture decisions are recorded under `docs/decisions/`.
