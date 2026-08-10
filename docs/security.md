# Security

Vulnerability reporting instructions and the private disclosure channel are defined in the repository [Security Policy](../SECURITY.md). Public Issues must not contain vulnerability details, credentials, customer data, private URLs, or proprietary platform output.

Package construction uses tracked-file allowlists, rejects file and parent-directory symlinks, writes deterministic safe ZIP paths, and excludes reports, evals, tests, caches, runs, customer data, and machine-local paths. Verification rejects traversal, absolute paths, symlinks, sensitive names/content, legal omissions, manifest drift, multi-Skill adapter archives, nondeterministic hashes, broken `pyproject.toml` data paths, missing route entries, and provider identity mismatches. Installation smoke runs each archive's own `pip install .` in a fresh environment before executing its route and provider wrapper.

Diagnosis accepts only explicit public HTTP(S) canonical URLs. SSRF, redirect, content type, response size, timeout, and file-descriptor gates bound retrieval. Content, discovery, and measurement never access the network. Measurement reads supplied trial records and performs no account access, browser automation, connector call, or continuous monitoring. Artifact publication is atomic. No command needs secrets or an external service.

Source URIs written to public artifacts must be absolute, omit user information and credential-bearing query parameters, and discard fragments during normalization. Diagnosis applies the narrower canonical public-URL policy to HTTP(S) evidence. Inputs that violate these boundaries fail before a run directory is published.

Runtime JSON input uses one strict parser that rejects `NaN`, `Infinity`, `-Infinity`, and finite-range overflow such as `1e9999`. JSON-LD containing those values remains counted as an observed script and never increases the valid JSON-LD or extraction signal counts.

Discover, Diagnose, Content, and Measure briefs use the same lexical no-follow descriptor walk. Every directory and the final file are opened with `O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC`; the final descriptor must identify a regular bounded file, and all bytes are read from that descriptor. FIFO input, file or parent symlinks, path replacement, and growth beyond the byte limit are rejected. On macOS, the reader recognizes only the root-owned `/var -> /private/var` system alias and then resumes the no-follow walk from `/private/var`; user-controlled parent and final symlinks remain rejected.
