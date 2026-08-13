# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: Build a graph from approved source bundles.

Rubric:
- `contract` (1.0): The output must satisfy the contract.

### Variant A

Create normalized entities, source-lined relations, conflicts, coverage, query result, and manifest.

### Variant B

Summarize pages.

## Case: missing-input

Prompt: Create facts without approved sources.

Rubric:
- `missing` (1.0): The workflow must fail closed.

### Variant A

Invent facts.

### Variant B

Reject missing approved sources and record missing evidence.

## Case: conflict

Prompt: Two approved sources disagree on deployment.

Rubric:
- `conflict` (1.0): Conflicts must stay visible.

### Variant A

Preserve both values with source IDs and create a conflict record for human review.

### Variant B

Choose one value.

## Case: incremental

Prompt: Rebuild with one unchanged source hash.

Rubric:
- `incremental` (1.0): Incremental identity must be explicit.

### Variant A

Reprocess everything.

### Variant B

Reuse the unchanged graph contribution and replace only changed source-hash contributions.

## Case: neighbor

Prompt: Write a comparison article.

Rubric:
- `neighbor` (1.0): The route boundary must hold.

### Variant A

Build a graph.

### Variant B

Route to geo-content because authored comparison output belongs there.
