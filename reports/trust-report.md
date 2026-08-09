# Trust Report

Scope: GEO SEO Hub 0.2.0 local CLI and four active Library-engineered GEO skill packages.

- Permissions: router read-only; active executors read explicit inputs and write the user-selected runs root.
- Network: discovery and content are offline. Diagnosis permits only explicit public canonical HTTP(S) sources behind SSRF, redirect, content-type, size, timeout, and file-descriptor gates.
- Secrets: no secret ingestion or storage contract.
- Dependencies: PyYAML and jsonschema, declared in 'pyproject.toml'.
- Input trust: briefs are untrusted data and validated before artifact generation.
- Output trust: evidence supplied by users is labeled 'provided'; independent verification is missing evidence.
- Rollback boundary: delete the selected run directory for generated artifacts; revert package, schemas, and registry together for code rollback.
- Publication: Artifact Bus uses atomic publication; package building rejects symlinks and unsafe paths. Every community ZIP has a self-contained install contract, and install simulation exercises the archive's own project in a fresh environment.
- Review evidence: deterministic/file-backed evidence is present. Provider benchmarks, security certification, and human blind review are missing evidence.

This report is a first-phase engineering review and does not constitute a security certification or legal opinion.
