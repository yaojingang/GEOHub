# Security Trust Report

- OK: `True`
- Scanned files: `21`
- Scripts: `1`
- Internal script modules: `0`
- Secret findings: `0`
- Network-capable scripts: `1`
- Network policy covered scripts: `1`
- Network policy missing scripts: `0`
- File-write scripts: `1`
- Permission approvals: `3 / 3`
- Permission approval gaps: `0`
- CLI help smoke checked: `1`
- CLI help smoke failures: `0`
- Interactive scripts: `0`
- Package hash scope: `source-contract-without-generated-reports`
- Package hash files: `21`
- Package SHA256: `b2adc9ee01f38120c55b4d7e66c00f5116dda5f2e3735f61199cf7a14daea990`

## Failures

- None

## Warnings

- No dependency or lock file detected

## Dependency Evidence

- Files: `none`
- Pinned entries: `0`
- Unpinned entries: `0`

## Network Policy

- Policy file: `security/network_policy.json`
- Present: `True`
- Covered scripts: `1`
- Missing scripts: `none`
- Mismatches: `0`

## Permission Governance

- Policy file: `security/permission_policy.json`
- Present: `True`
- Required capabilities: `file_write, network, subprocess`
- Approved capabilities: `file_write, network, subprocess`
- Missing approvals: `none`
- Invalid approvals: `none`
- Expired approvals: `none`

## CLI Help Smoke

- Enabled: `True`
- Timeout seconds: `5.0`
- Checked scripts: `1`
- Passed scripts: `1`
- Failed scripts: `none`

## Script Surface

| Script | Interface | Declared | Argparse | Main Guard | Input | Network | File Write | Subprocess | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scripts/run_site_diagnose.py | cli | True | True | True | False | True | True | True | The wrapper validates public HTTP input and delegates to the installed bounded crawler. |
