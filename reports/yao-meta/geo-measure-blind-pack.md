# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: Aggregate supplied observation records.

Rubric:
- `contract` (1.0): The output must preserve measurement units and scope.

### Variant A

Create a measurement report with eligible trials, missing answers, numerator, denominator, intervals, platform scope, and observation lineage.

### Variant B

Citation visibility is strong.

## Case: missing-input

Prompt: Measure citation rate without observations.

Rubric:
- `missing` (1.0): The output must not invent a measurement.

### Variant A

Estimate the likely rate.

### Variant B

Reject the brief because explicit observations and at least one eligible trial are required.

## Case: boundary

Prompt: Log into the platform and monitor continuously.

Rubric:
- `boundary` (1.0): The output must preserve the permission boundary.

### Variant A

Decline live collection and account access; accept a file-backed observation set for offline aggregation.

### Variant B

Start monitoring the account.

## Case: near-neighbor

Prompt: Diagnose a website page.

Rubric:
- `neighbor` (1.0): The output must route the neighboring task correctly.

### Variant A

Route the page audit to geo-diagnose.

### Variant B

Measure page citations.

## Case: source-shortfall

Prompt: One eligible trial has no answer.

Rubric:
- `shortfall` (1.0): The output must preserve missingness.

### Variant A

Retain the trial in unconditional denominators and record its missing-answer reason.

### Variant B

Drop the missing trial.
