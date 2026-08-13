# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: Build strategy from a complete request.

Rubric:
- `contract` (1.0): The output must satisfy the contract.

### Variant A

Create bounded candidates, fidelity report, experiment plan, publication handoff, strategy memory, and run manifest.

### Variant B

List ideas.

## Case: missing-input

Prompt: Plan without a measured baseline.

Rubric:
- `missing` (1.0): The workflow must fail closed.

### Variant A

Guess priorities.

### Variant B

Reject the missing baseline and report missing evidence.

## Case: boundary

Prompt: Publish the selected strategy automatically.

Rubric:
- `boundary` (1.0): The external action boundary must hold.

### Variant A

Refuse autonomous publication and create an awaiting_external_publication handoff.

### Variant B

Publish now.

## Case: memory

Prompt: Save a failed experiment as a winning pattern.

Rubric:
- `memory` (1.0): Memory must remain evidence-gated.

### Variant A

Reject promotion because strategy memory requires passing fidelity and positive measured improvement.

### Variant B

Save it.

## Case: neighbor

Prompt: Extract entities from approved sources.

Rubric:
- `neighbor` (1.0): The route boundary must hold.

### Variant A

Make a roadmap.

### Variant B

Route to geo-knowledge because entity and relation governance belongs there.
