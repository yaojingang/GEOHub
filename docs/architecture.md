# Architecture

GEO SEO Hub separates intent resolution, deterministic execution, and artifact validation. The current runtime is GEO-first; the shared evidence, query, content, schema, and Artifact Bus layers form the compatibility boundary for future SEO capabilities.

1. `registry/skills.yaml` declares five active and three planned capabilities.
2. `registry/research-evidence.json` maps the fixed 54-paper and two-dataset audit to source-resolved principles, causal status, platform scope, proxy variables, controls, and limitations.
3. `geo_seo_hub.router` resolves one smallest skill or one exact stable workflow DAG under `skills/RESOLVER.md`.
4. Active executors validate bounded inputs and publish protocol `1.0.0` runs through the Artifact Bus.
5. `research-context.json` carries the applicable research boundary into each run. Discover normalizes query dimensions, Diagnose separates eligibility, selection proxies, and unobserved absorption, Content classifies evidence units, and Measure reports complete descriptive denominators and intervals.
6. JSON Schemas, quality reports, evidence ledgers, and atomic manifests preserve source gaps and replay boundaries.

`geo-discover`, `geo-content`, and `geo-measure` are offline. `geo-diagnose` supports replay snapshots and a tightly bounded explicit-source network mode. `geo-strategy`, `geo-knowledge`, and `geo-publish` have null entrypoints and cannot execute.

Dedicated SEO providers are not registered in version 0.3.0. Future SEO additions must use distinct Registry entries and preserve the same evidence, permission, output, and degradation contracts before they become runnable.
