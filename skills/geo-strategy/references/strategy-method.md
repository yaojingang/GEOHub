# Strategy optimization method

## Inputs

Supply goals, audience, constraints, risks, brand rules, metric weights that sum to one, a measured baseline with a stable query panel, diagnosis actions, approved evidence IDs, and an observation window.

## Controlled loop

1. Generate two to four intervention candidates.
2. Record the action diff and metric-level expected impact for every candidate.
3. Run constraint, brand, evidence, and risk fidelity checks.
4. Approve one candidate for offline handoff.
5. Require a human-approved external publication receipt.
6. Observe the unchanged panel after the declared window.
7. Promote strategy memory only when fidelity passed and weighted measured improvement is positive.
8. Stop after two consecutive observations without positive improvement or any fidelity failure.

Expected impact values are planning estimates. They carry no external-effect status.
