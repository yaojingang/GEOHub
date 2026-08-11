# Routing Contract

The registry at 'registry/skills.yaml' is the source of truth.

- 'active': runnable only when 'entry' points to an existing skill.
- 'pending-implementation': reserved protocol surface with no runnable entry.
- 'planned': roadmap intent with no runnable entry.
- 'active_placeholder' must remain false for every unavailable route.

Routing uses normalized phrase matching. A broad or unmatched GEO request falls back to 'geo'. Equal top scores are resolved by registry order and disclosed through the result's 'alternatives' field.

The router may suggest 'geo-discover' when a downstream route is unavailable. A suggestion is not an assertion that discovery fulfills the unavailable stage.

`geo-discover`, `geo-diagnose`, `geo-content`, `geo-measure`, and `seo` are active alongside the `geo` umbrella router. Discovery covers intent and query research; diagnosis covers evidence-lined brand, site, and page audits; content covers title, explainer, comparison, ranking, page-blueprint, refine, and article-friendly requests; measurement aggregates explicit offline observation records with complete denominators and intervals; SEO converts one request into a bounded, evidence-aware work plan.

`geo-strategy`, `geo-knowledge`, and `geo-publish` remain planned roadmap routes with no runnable entry.
# Routing contract

`registry/skills.yaml` and `skills/RESOLVER.md` define route ownership. Existing response keys remain stable. `workflow` is optional and appears only for an exact supported multi-intent recipe. Planned entries have no entrypoint, stay non-runnable, and expose a domain-nearest active suggestion, `required_inputs`, and `closest_v0_artifact`.
