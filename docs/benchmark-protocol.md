# GEO Benchmark Protocol 1.0

## Evidence levels

A five-query recorded fixture validates Schema, parsing, duplicate detection, metric reconstruction, semantic digest stability, and package execution. It carries the statement `recorded fixtures do not prove live engine visibility`.

A public outcome comparison uses at least 30 queries across brand, category, compare, evaluate, and act intents, with at least six queries per intent. Each query runs three times per engine. Baseline and candidate observations use the same panel version, locale, region, session policy, login state, and a 24-hour collection window.

## Collection boundary

Accepted methods are `manual_export`, `approved_api`, and `recorded_fixture`. The collector records identity, permission scope, source note, engine, visible model or `unknown`, observed time, locale, session policy, timepoint, and repetition. Material that required bypassing login, CAPTCHA, anti-automation, or regional controls is rejected.

## Metrics and comparison

Every metric publishes numerator, denominator, missing count, query-level raw components, and per-engine results. Missing observations never improve a score. Reports include:

- mention rate;
- target-source inclusion rate;
- target citation share;
- position-weighted visibility;
- answer coverage;
- observation coverage;
- missing observation rate.

Outcome comparisons report engine strata, effect size, and bootstrap confidence intervals. Low sample sizes receive descriptive statistics and a missing-evidence statement. Cross-engine reporting preserves each engine and the source of any weighting.
