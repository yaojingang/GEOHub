# ADR 0004: Provider and privacy boundary

Status: Accepted.

Core runs are file-backed. Provider execution is optional, credential-free in artifacts, budget-bounded, and fails closed when configuration is absent. Adoption aggregation consumes allowlisted lineage metadata. Customer payloads, prompts, raw answers, and credentials are excluded.
