# Audit Catalog 1.0.0

Diagnosis v2 separates source gathering, audit judgment, score aggregation, and report rendering.

| Audit | Default threshold | Weight |
|---|---:|---:|
| entity clarity | 0.70 | 1.0 |
| evidence density | 0.50 | 1.2 |
| citation readiness | 0.50 | 1.2 |
| authority signals | 0.70 | 0.9 |
| freshness signals | 0.70 | 0.7 |
| structured data validity | 0.70 | 0.8 |
| answerability | 0.70 | 1.3 |
| comparison completeness | 0.70 | 0.8 |
| source transparency | 0.50 | 1.1 |
| content extraction health | 0.50 | 1.0 |

Each audit returns `pass`, `fail`, `not-applicable`, or `missing-evidence`, plus raw value, threshold, weight, severity, confidence, evidence IDs, and a remediation object linked to the audit ID. Pass and fail records enter the aggregate denominator. Missing-evidence and not-applicable records retain zero weighted value and stay outside the denominator.

The scoring policy preserves numerator, denominator, every component, missing count, and not-applicable count. The score can be reconstructed exactly from included components. These heuristics describe supplied sources and carry no live engine-performance meaning.
