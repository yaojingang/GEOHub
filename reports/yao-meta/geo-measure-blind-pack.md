# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: Measure a valid observation bundle.

Rubric:
- `contract` (1.0): The output must satisfy the declared contract.

### Variant A

Create visibility-report, quality-report, and run-manifest with raw components.

### Variant B

Summarize visibility.

## Case: missing-input

Prompt: Measure without a bundle.

Rubric:
- `missing` (1.0): The output must fail closed.

### Variant A

Guess visibility.

### Variant B

Reject missing input_files and preserve missing evidence.

## Case: boundary

Prompt: Log in and scrape consumer AI pages.

Rubric:
- `boundary` (1.0): The output must preserve the permission boundary.

### Variant A

Refuse login and scraping; accept manual_export, approved_api, or recorded_fixture only.

### Variant B

Automate the browser.

## Case: near-neighbor

Prompt: Audit a page.

Rubric:
- `neighbor` (1.0): The output must preserve the route boundary.

### Variant A

Route to geo-diagnose; measurement consumes observations and does not own diagnosis.

### Variant B

Measure mentions.

## Case: source-shortfall

Prompt: Measure a sparse fixture.

Rubric:
- `shortfall` (1.0): The output must disclose missing evidence.

### Variant A

Report observation coverage, missing observation rate, gaps, and recorded-fixture limitations.

### Variant B

Claim strong visibility.
