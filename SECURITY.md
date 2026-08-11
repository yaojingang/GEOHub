# Security Policy

## Supported version

GEOHub `0.3.x` is experimental. Security fixes are applied to the latest commit on `main`; users should reproduce a report against that revision when practical.

## Report a vulnerability

Use [GitHub Private Vulnerability Reporting](https://github.com/yaojingang/GEOHub/security/advisories/new) for suspected vulnerabilities. This private channel is intended for reproducible technical details, proof-of-concept material, and coordinated disclosure.

Do not disclose vulnerability details, credentials, customer data, private URLs, or proprietary platform output in a public Issue. General hardening suggestions that contain no sensitive details may use the public issue tracker.

The maintainer will triage reports according to severity, reproducibility, and affected release scope. Acknowledgment and remediation timing depend on the report and do not create a support or response-time commitment.

## Scope

Reports may cover the Python runtime, Skill routing, Artifact Bus publication, input and archive handling, offline measurement aggregation, package installation, or accidental disclosure through generated artifacts. Third-party platform behavior, live collection, and unsupported planned integrations remain outside the executable `0.3.x` scope.
