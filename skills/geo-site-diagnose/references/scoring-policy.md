# Scoring policy 1.0.0

| Dimension | Weight |
| --- | ---: |
| AI access and technical discovery | 15 |
| Content architecture and coverage | 10 |
| Entity clarity and consistency | 12 |
| Answerability | 15 |
| Evidence and citation readiness | 16 |
| Authority and trust | 12 |
| Structure and extractability | 12 |
| Freshness and maintenance | 8 |

Each check records raw value, threshold, dimension weight, status, score, evidence IDs, and remediation. Pass and fail checks enter the denominator. `missing-evidence` lowers diagnostic confidence. `not-applicable` leaves the denominator. Page and site scores are integer readiness heuristics reconstructed from visible components. Homepage failure suppresses the overall score.

Scores do not represent live engine ranking, recall, citation probability, traffic, conversion, or revenue. A high score means the observed representative-page signals are comparatively complete within this policy.
