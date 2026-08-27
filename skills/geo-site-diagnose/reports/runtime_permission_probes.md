# Runtime Permission Probes

Runtime permission probes verify that generated target adapters expose high-permission capabilities, make native-enforcement limits explicit, and link installer enforcement evidence when available.

## Summary

- OK: `True`
- Targets probed: `3`
- Passed: `3`
- Failed: `0`
- Native enforcement targets: `0`
- Explicit metadata fallbacks: `3`
- Installer enforcement source: `package-mismatch`
- Installer-enforced targets: `0`
- Installer permission failures: `0`
- World-class native evidence ready: `False`
- Required capabilities: `file_write, network, subprocess`

| Target | Status | Assurance | Native Enforcement | Metadata Fallback | Installer Enforcement | Residual Risk |
| --- | --- | --- | --- | --- | --- | --- |
| `openai` | `pass` | `metadata-fallback-explicit` | `False` | `True` | `package-mismatch` | Client-native permission enforcement is not provided by this target; installer or operator must honor metadata. |
| `claude` | `pass` | `metadata-fallback-explicit` | `False` | `True` | `package-mismatch` | Client-native permission enforcement is not provided by this target; installer or operator must honor metadata. |
| `generic` | `pass` | `metadata-fallback-explicit` | `False` | `True` | `package-mismatch` | Client-native permission enforcement is not provided by this target; installer or operator must honor metadata. |

## Installer Enforcement

- Source: `reports/install-simulation.json`
- Source status: `package-mismatch`
- Package dir matches probe: `False`

Installer enforcement means the package install simulation blocks missing capability approvals or target enforcement notes. It is supporting local distribution evidence, not proof of target-client native enforcement.

## Failures

- None

## Reviewer Note

A passing probe means the target contract is explicit and auditable. It does not claim that a host client enforces permissions natively.
