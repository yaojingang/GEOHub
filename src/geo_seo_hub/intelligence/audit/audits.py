from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


CATALOG_VERSION = "1.0.0"


@dataclass(frozen=True)
class AuditSpec:
    audit_id: str
    threshold: float
    weight: float
    remediation: str


AUDIT_CATALOG = {
    item.audit_id: item
    for item in (
        AuditSpec("entity-clarity", 0.70, 1.0, "Clarify the primary entity, page subject, and canonical name."),
        AuditSpec("evidence-density", 0.50, 1.2, "Attach important claims to named evidence and transparent methods."),
        AuditSpec("citation-readiness", 0.50, 1.2, "Add stable source references that can support answer citations."),
        AuditSpec("authority-signals", 0.70, 0.9, "Show accountable authorship, expertise, and organization details."),
        AuditSpec("freshness-signals", 0.70, 0.7, "Publish a meaningful reviewed or updated date where freshness matters."),
        AuditSpec("structured-data-validity", 0.70, 0.8, "Validate applicable structured data and align it with visible content."),
        AuditSpec("answerability", 0.70, 1.3, "Provide a self-contained answer with clear headings and sufficient visible detail."),
        AuditSpec("comparison-completeness", 0.70, 0.8, "Use consistent comparison dimensions and disclose missing evidence."),
        AuditSpec("source-transparency", 0.50, 1.1, "Expose sources, methods, and claim boundaries close to the supported content."),
        AuditSpec("content-extraction-health", 0.50, 1.0, "Use semantic landmarks, headings, lists, or tables for reliable extraction."),
    )
}


def evaluate_audit(
    audit_id: str,
    raw_value: float | None,
    *,
    applicable: bool,
    evidence_ids: Iterable[str],
) -> dict[str, Any]:
    if audit_id not in AUDIT_CATALOG:
        raise ValueError(f"unknown audit ID: {audit_id}")
    spec = AUDIT_CATALOG[audit_id]
    ids = sorted(set(evidence_ids))
    if not applicable:
        status = "not-applicable"
        severity = "info"
        confidence = 1.0
        normalized = None
    elif raw_value is None or not ids:
        status = "missing-evidence"
        severity = "opportunity"
        confidence = 0.0
        normalized = None
    else:
        normalized = round(float(raw_value), 6)
        if not 0.0 <= normalized <= 1.0:
            raise ValueError(f"audit raw value is outside [0, 1]: {audit_id}")
        status = "pass" if normalized >= spec.threshold else "fail"
        severity = "info" if status == "pass" else "warning"
        confidence = 0.95
    return {
        "audit_id": audit_id,
        "catalog_version": CATALOG_VERSION,
        "status": status,
        "raw_value": normalized,
        "threshold": spec.threshold,
        "weight": spec.weight,
        "severity": severity,
        "confidence": confidence,
        "evidence_ids": ids,
        "remediation": {
            "audit_id": audit_id,
            "action": spec.remediation,
            "evidence_ids": ids,
        },
    }


def run_audit_catalog(observations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for observation in observations:
        evidence_id = observation.get("evidence_id")
        evidence_ids = [evidence_id] if evidence_id else []
        for audit_id in AUDIT_CATALOG:
            records.append(
                evaluate_audit(
                    audit_id,
                    observation["values"].get(audit_id),
                    applicable=observation["applicability"].get(audit_id, False),
                    evidence_ids=evidence_ids,
                )
            )
    return records
