# Architecture

GEO SEO Hub separates intent resolution, deterministic execution, and artifact validation. The current runtime is GEO-first; the shared evidence, query, content, schema, and Artifact Bus layers form the compatibility boundary for future SEO capabilities.

1. `registry/skills.yaml` declares active and planned capabilities.
2. `geo_seo_hub.router` resolves one smallest skill or one exact stable workflow DAG under `skills/RESOLVER.md`.
3. Active executors validate file-backed inputs and publish protocol `1.0.0` runs through the Artifact Bus.
4. JSON Schemas and quality reports preserve evidence gaps and replay boundaries.

`geo-discover` is offline. `geo-content` is offline. `geo-diagnose` supports replay snapshots and a tightly bounded explicit-source network mode. Planned capabilities have null entrypoints and cannot execute.

Dedicated SEO providers are not registered in version 0.2.0. Future SEO additions must use distinct Registry entries and preserve the same evidence, permission, output, and degradation contracts before they become runnable.
