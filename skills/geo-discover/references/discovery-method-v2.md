# Discovery Method v2

## Execution modes

- `legacy` reproduces the four template intents and remains the compatibility default.
- `deterministic` combines the template baseline with an entity, criteria, risk, and implementation question graph.
- `research` may derive hypothetical-document questions from evidence claims already approved in the input brief.
- `provider` accepts a runtime adapter with provider, model, prompt digest, tokens, cost, and bounded hypothesis text. A missing or failed adapter completes through the deterministic fallback and records degraded status.

## Candidate pipeline

1. Generate stable candidates for each seed, audience, and scenario.
2. Preserve generator, parent seed lineage, intent, audience, scenario, and evidence status.
3. Remove exact and high-similarity duplicates within the same intent and context.
4. Score coverage, relevance, novelty, evidence, and business fit as separate components.
5. Map each query to one initial asset opportunity and retain every score component.

Evidence score is `0` when the brief contains no evidence. Heuristic opportunity priority has no search-volume, conversion, or ranking meaning. The semantic digest excludes run timestamps and volatile lineage fields.

## Quality evidence

`evals/discovery/gold-labels.json` contains the synthetic two-annotator coverage fixture and its adjudication record. It validates pipeline coverage and does not establish real-market performance. Provider/model evidence and independent human outcome review remain missing evidence until governed results are attached.
