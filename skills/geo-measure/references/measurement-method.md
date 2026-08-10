# Measurement method

## Required observation unit

Each trial records a query ID, engine, interface, language, geography, collection time, model version, sample unit, eligibility, answer state, citation state, missing-answer or exclusion reason, and source URI. The normalized brief is the replay boundary.

## Denominators

- `answer_rate = answered eligible trials / eligible trials`
- `citation_rate = cited eligible trials / eligible trials`
- `conditional_citation_rate = cited eligible trials / answered eligible trials`

Eligible unanswered trials remain in the first two denominators. Excluded trials remain visible in total counts and exclusion reasons. Every computable proportion uses a Wilson score interval at the declared confidence level. A zero answered denominator produces `not-computable` for the conditional citation rate.

## Scope and interpretation

Platform strata use engine, interface, language, geography, model version, and sample unit. Collection bounds come from normalized timestamps. The current runtime reports descriptive measurements only. A randomized or quasi-experimental label preserves the requested design metadata and does not unlock a causal estimate.

Read `research-context.json` for source IDs, platform scope, proxy variables, controls, and limitations. Software tests validate the aggregation contract; they do not establish live-platform effectiveness.
