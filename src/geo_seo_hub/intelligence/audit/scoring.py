from __future__ import annotations

from typing import Any, Iterable


SCORING_POLICY_VERSION = "1.0.0"


def score_audits(audits: Iterable[dict[str, Any]]) -> dict[str, Any]:
    components = []
    numerator = 0.0
    denominator = 0.0
    for audit in audits:
        included = audit["status"] in {"pass", "fail"}
        score_value = 1.0 if audit["status"] == "pass" else 0.0
        weight = float(audit["weight"])
        weighted_value = score_value * weight if included else 0.0
        if included:
            numerator += weighted_value
            denominator += weight
        components.append(
            {
                "audit_id": audit["audit_id"],
                "status": audit["status"],
                "weight": weight,
                "score_value": score_value if included else None,
                "weighted_value": round(weighted_value, 6),
                "included": included,
            }
        )
    score = round(100 * numerator / denominator, 6) if denominator else 0.0
    return {
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "score": score,
        "numerator": round(numerator, 6),
        "denominator": round(denominator, 6),
        "missing_count": sum(item["status"] == "missing-evidence" for item in components),
        "not_applicable_count": sum(item["status"] == "not-applicable" for item in components),
        "components": components,
    }
