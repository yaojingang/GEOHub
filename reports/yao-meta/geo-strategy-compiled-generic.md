# Compiled Targets

- OK: `True`
- Targets: `1`
- Pass: `1`
- Warn: `0`
- Block: `0`

## Target Transforms

| Target | Status | Native Surface | Adapter Mode | Permissions | Degradation | Generated Files |
| --- | --- | --- | --- | --- | --- | --- |
| `generic` | `pass` | Agent Skills compatible neutral package | `agent-skills-compatible` | `none` | `neutral-source` | targets/generic/adapter.json |

## Native Behavior Contracts

### generic

- Native surface: Agent Skills compatible neutral package
- Activation: Use SKILL.md name and description; consumers decide automatic or manual activation.
- Resources: Preserve references, scripts, assets, evals, reports, and adapter metadata as relative package resources.
- Scripts: Expose script and permission metadata for downstream clients or installers to enforce.
- Permission enforcement: `consumer-enforced-or-metadata-only`; native enforcement `False`
- Review artifacts: targets/generic/adapter.json, reports/review-studio.html


## Failures

- None

## Warnings

- None
