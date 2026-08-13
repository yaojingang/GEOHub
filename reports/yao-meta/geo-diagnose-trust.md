# Security Trust Report

- OK: `True`
- Scanned files: `10`
- Scripts: `1`
- Internal script modules: `0`
- Secret findings: `0`
- Network-capable scripts: `0`
- Network policy covered scripts: `0`
- Network policy missing scripts: `0`
- File-write scripts: `0`
- Permission approvals: `0 / 0`
- Permission approval gaps: `0`
- CLI help smoke checked: `0`
- CLI help smoke failures: `0`
- Interactive scripts: `0`
- Package hash scope: `source-contract-without-generated-reports`
- Package hash files: `10`
- Package SHA256: `4b2fbf2f806119c625c5b41ce7a66b4f59b3e07d7cf91a33eaffa2352b48a134`

## Failures

- None

## Warnings

- No dependency or lock file detected
- CLI scripts without argparse/help surface: scripts/run_diagnose.py

## Dependency Evidence

- Files: `none`
- Pinned entries: `0`
- Unpinned entries: `0`

## Network Policy

- Policy file: `security/network_policy.json`
- Present: `False`
- Covered scripts: `0`
- Missing scripts: `none`
- Mismatches: `0`

## Permission Governance

- Policy file: `security/permission_policy.json`
- Present: `False`
- Required capabilities: `none`
- Approved capabilities: `none`
- Missing approvals: `none`
- Invalid approvals: `none`
- Expired approvals: `none`

## CLI Help Smoke

- Enabled: `True`
- Timeout seconds: `5.0`
- Checked scripts: `0`
- Passed scripts: `0`
- Failed scripts: `none`

## Script Surface

| Script | Interface | Declared | Argparse | Main Guard | Input | Network | File Write | Subprocess | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scripts/run_diagnose.py | cli | False | False | True | False | False | False | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
