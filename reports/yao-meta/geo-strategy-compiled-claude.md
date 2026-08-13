# Compiled Targets

- OK: `True`
- Targets: `1`
- Pass: `1`
- Warn: `0`
- Block: `0`

## Target Transforms

| Target | Status | Native Surface | Adapter Mode | Permissions | Degradation | Generated Files |
| --- | --- | --- | --- | --- | --- | --- |
| `claude` | `pass` | Claude-compatible neutral source folder with adapter notes | `neutral-source-plus-adapter` | `none` | `neutral-source-plus-adapter` | targets/claude/adapter.json, targets/claude/README.md |

## Native Behavior Contracts

### claude

- Native surface: Claude-compatible neutral source folder with adapter notes
- Activation: Use SKILL.md frontmatter description as the primary activation contract and adapter.json for review metadata.
- Resources: Preserve the source tree directly; write target notes in targets/claude/README.md.
- Scripts: Scripts remain local package resources and must be reviewed through trust and permission reports before use.
- Permission enforcement: `metadata-fallback`; native enforcement `False`
- Review artifacts: targets/claude/README.md, targets/claude/adapter.json, reports/review-studio.html


## Failures

- None

## Warnings

- None
