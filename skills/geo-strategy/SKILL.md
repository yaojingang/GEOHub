---
name: geo-strategy
description: Build an offline GEO optimization plan from explicit goals, diagnosis actions, approved evidence IDs, and a measured baseline. Use for GEO strategy, roadmap, experiment planning, intervention candidates, 策略, 路线图, and 优化实验. Exclude autonomous publication, fabricated outcome evidence, and memory promotion without positive external measurement.
---

# GEO Strategy

## Workflow

1. Read `references/strategy-method.md` and prepare the complete file-backed request.
2. Run `python3 scripts/run_strategy.py --input <request.json> --output <runs-root>`.
3. Review all candidates and the fidelity report; choose an offline-approved candidate.
4. Hand `publication-handoff.json` to an authorized publisher and wait for a verified publication receipt.
5. Measure the unchanged query panel after the declared window. Promote memory only when fidelity passed and the weighted metric delta is positive.

## Output contract

Produce the input snapshot, bounded candidates, fidelity report, experiment plan, publication handoff, strategy memory, quality report, lineage, and manifest. Read `references/output-contract.md` before approval.

## Boundaries

Execution stays offline. The Skill never publishes, logs in, claims external impact, or promotes an unmeasured intervention. External publication and observation stay marked `missing evidence` until verified artifacts arrive.
