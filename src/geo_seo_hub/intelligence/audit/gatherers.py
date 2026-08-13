from __future__ import annotations

import re
from typing import Any


AUDIT_IDS = (
    "entity-clarity",
    "evidence-density",
    "citation-readiness",
    "authority-signals",
    "freshness-signals",
    "structured-data-validity",
    "answerability",
    "comparison-completeness",
    "source-transparency",
    "content-extraction-health",
)


def _bounded_ratio(numerator: float, denominator: float) -> float:
    return round(max(0.0, min(1.0, numerator / denominator if denominator else 0.0)), 6)


def gather_page_observations(
    metrics: dict[str, Any],
    *,
    source_id: str,
    evidence_id: str,
) -> dict[str, Any]:
    """Translate parser metrics into judgment-free normalized observations."""
    text = metrics["visible_text"]
    evidence_signal = bool(re.search(r"source|reference|citation|method|数据|来源|参考|方法", text, re.I))
    authority_signal = bool(re.search(r"author|editor|expert|about|contact|作者|专家|关于|联系", text, re.I))
    freshness_signal = bool(re.search(r"\b20\d{2}(?:[-/.年]\d{1,2})?|updated|last modified|更新", text, re.I))
    comparison_signal = bool(re.search(r"compare|versus|\bvs\.?\b|对比|比较", text, re.I)) or metrics["table_count"] > 0
    semantic_signals = metrics["main_count"] + metrics["article_count"] + metrics["list_count"] + metrics["table_count"]
    values = {
        "entity-clarity": _bounded_ratio(int(bool(metrics["title"])) + int(bool(metrics["headings"]["h1"])), 2),
        "evidence-density": _bounded_ratio(int(evidence_signal) + min(2, metrics["external_link_count"]), 3),
        "citation-readiness": _bounded_ratio(int(evidence_signal) + int(metrics["external_link_count"] > 0), 2),
        "authority-signals": float(authority_signal),
        "freshness-signals": float(freshness_signal),
        "structured-data-validity": _bounded_ratio(metrics["valid_json_ld_count"], max(1, metrics["json_ld_count"])),
        "answerability": _bounded_ratio(int(bool(metrics["headings"]["h1"])) + int(metrics["visible_text_length"] >= 300) + int(semantic_signals > 0), 3),
        "comparison-completeness": _bounded_ratio(int(comparison_signal) + int(metrics["table_count"] > 0), 2),
        "source-transparency": _bounded_ratio(int(evidence_signal) + int(metrics["external_link_count"] > 0), 2),
        "content-extraction-health": _bounded_ratio(min(3, semantic_signals) + int(bool(metrics["headings"]["h2"])), 4),
    }
    applicability = {audit_id: True for audit_id in AUDIT_IDS}
    applicability["comparison-completeness"] = comparison_signal
    return {
        "source_id": source_id,
        "evidence_id": evidence_id,
        "values": values,
        "applicability": applicability,
    }


def gather_brand_observations(provided_evidence_ids: list[str]) -> dict[str, Any]:
    has_evidence = bool(provided_evidence_ids)
    values: dict[str, float | None] = {audit_id: None for audit_id in AUDIT_IDS}
    values["entity-clarity"] = 1.0 if has_evidence else None
    values["evidence-density"] = min(1.0, len(provided_evidence_ids) / 4) if has_evidence else None
    values["source-transparency"] = 1.0 if has_evidence else None
    applicability = {audit_id: False for audit_id in AUDIT_IDS}
    for audit_id in ("entity-clarity", "evidence-density", "source-transparency"):
        applicability[audit_id] = True
    return {
        "source_id": "brand-input",
        "evidence_id": provided_evidence_ids[0] if provided_evidence_ids else None,
        "values": values,
        "applicability": applicability,
    }
