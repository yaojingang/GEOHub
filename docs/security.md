# Security

Vulnerability reporting instructions and the private disclosure channel are defined in the repository [Security Policy](../SECURITY.md). Public Issues must not contain vulnerability details, credentials, customer data, private URLs, or proprietary platform output.

Package construction uses tracked-file allowlists, rejects file and parent-directory symlinks, writes deterministic safe ZIP paths, and excludes reports, caches, runs, customer data, and machine-local paths. The source snapshot carries tests and public evals; runtime adapters omit them. Verification rejects traversal, absolute paths, symlinks, sensitive names/content, legal omissions, manifest drift, multi-Skill adapter archives, nondeterministic hashes, broken `pyproject.toml` data paths, missing route entries, and provider identity mismatches. Installation smoke runs each archive's own `pip install .` in a fresh environment before executing its route and provider wrapper.

Diagnosis accepts only explicit public HTTP(S) canonical URLs. SSRF, redirect, content type, response size, timeout, and file-descriptor gates bound retrieval. Content, discovery, measurement, strategy, and knowledge never access the network. Artifact publication is atomic. Deterministic commands need no secret or external service.

Measurement accepts one bounded engine observation bundle. Real observations require `manual_export` or `approved_api` collection evidence; recorded fixtures remain synthetic proof. The executor validates panel membership, observation slots, collection methods, HTTP(S) citation URIs, and target-source normalization before scoring.

Runtime JSON input uses one strict parser that rejects `NaN`, `Infinity`, `-Infinity`, and finite-range overflow such as `1e9999`. JSON-LD containing those values remains counted as an observed script and never increases the valid JSON-LD or extraction signal counts.

All executor inputs use the same lexical no-follow descriptor walk. Every directory and the final file are opened with `O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC`; the final descriptor must identify a regular bounded file, and all bytes are read from that descriptor. FIFO input, file or parent symlinks, path replacement, and growth beyond the byte limit are rejected. On macOS, the reader recognizes only the root-owned `/var -> /private/var` system alias and then resumes the no-follow walk from `/private/var`; user-controlled parent and final symlinks remain rejected.

Local provenance cannot assert a trusted builder. The release workflow separates an unprivileged hash-locked build job from the OIDC-enabled attestation job. Every referenced GitHub Action uses a full commit SHA, checkout credentials are not persisted, tags must equal `v$(cat VERSION)`, and the transferred artifact digest list is verified before attestation. CI attestation execution and external `gh attestation verify` output remain missing evidence until a workflow run produces them.
