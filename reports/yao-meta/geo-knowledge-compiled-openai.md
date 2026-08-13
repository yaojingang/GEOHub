# Compiled Targets

- OK: `True`
- Targets: `1`
- Pass: `1`
- Warn: `0`
- Block: `0`

## Target Transforms

| Target | Status | Native Surface | Adapter Mode | Permissions | Degradation | Generated Files |
| --- | --- | --- | --- | --- | --- | --- |
| `openai` | `pass` | OpenAI-style interface metadata plus neutral Agent Skills source | `metadata-adapter` | `none` | `metadata-adapter` | targets/openai/adapter.json, targets/openai/agents/openai.yaml |

## Native Behavior Contracts

### openai

- Native surface: OpenAI-style interface metadata plus neutral Agent Skills source
- Activation: Use frontmatter description for catalog routing and targets/openai/agents/openai.yaml for display name, default prompt, and compatibility metadata.
- Resources: Ship the neutral source tree and expose OpenAI-facing interface metadata as a generated companion file.
- Scripts: Keep scripts as local package resources; expose help-smoke and permission metadata for reviewer approval before execution.
- Permission enforcement: `metadata-only`; native enforcement `False`
- Review artifacts: targets/openai/agents/openai.yaml, targets/openai/adapter.json, reports/review-studio.html


## Failures

- None

## Warnings

- None
