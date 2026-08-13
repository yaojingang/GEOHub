from __future__ import annotations

import hashlib
import json
from typing import Any

from .audits import CATALOG_VERSION
from .scoring import SCORING_POLICY_VERSION, score_audits


def build_audit_extension(
    audit_results: list[dict[str, Any]],
    *,
    execution_mode: str,
    failures: list[str],
) -> dict[str, Any]:
    audit_score = score_audits(audit_results)
    execution = {
        "mode": execution_mode,
        "status": "degraded" if failures else "completed",
        "failures": failures,
    }
    semantic_payload = {
        "audit_catalog_version": CATALOG_VERSION,
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "audit_results": audit_results,
        "audit_score": audit_score,
        "execution": execution,
    }
    semantic_digest = hashlib.sha256(
        json.dumps(
            semantic_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return {**semantic_payload, "semantic_digest": semantic_digest}
