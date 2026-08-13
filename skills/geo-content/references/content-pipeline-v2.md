# Content Pipeline v2

Non-legacy execution produces a versioned, offline pipeline report alongside the existing content artifacts.

1. Research bundle collects approved evidence, source snapshot digest, audience, and evidence gaps.
2. Perspective plan records decision questions and counter-questions.
3. Outline binds every section to purpose, question, claim IDs, and source IDs.
4. Drafting continues through the existing bounded content modes and factual-claim rules.
5. Claim verification writes `claim-map.json` with support status, source IDs, confidence, location, and repair action.
6. Polish records structure, claim-boundary, and responsive artifact checks without changing factual support.

`content-pipeline.json` carries a semantic digest over stable pipeline fields. Provider mode has no packaged adapter and completes through the deterministic path with a degraded execution record. Research mode consumes only sources already approved and snapshotted in the brief.
