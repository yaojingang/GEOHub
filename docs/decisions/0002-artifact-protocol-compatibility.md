# ADR 0002: Artifact protocol compatibility

Status: Accepted.

JSON Schema remains the normative `0.x` contract. Artifact protocol `1.0.0` continues across 0.5.0. New artifacts are additive and every executor publishes atomically through the Artifact Bus. Existing public imports, JSON stdout/stderr, exit codes, and legacy execution defaults remain supported.
