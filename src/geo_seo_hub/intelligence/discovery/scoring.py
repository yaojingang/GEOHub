from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .clustering import normalized_similarity
from .strategies import DiscoveryCandidate


ASSET_BY_INTENT = {
    "learn": "article",
    "compare": "comparison",
    "evaluate": "faq",
    "act": "landing-page",
}


def _stable_id(prefix: str, *parts: str) -> str:
    return f"{prefix}-{hashlib.sha256(chr(31).join(parts).encode('utf-8')).hexdigest()[:12]}"


def _round(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def build_v2_maps(
    brief: dict[str, Any],
    run_id: str,
    candidates: Iterable[DiscoveryCandidate],
    execution: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    evidence = 1.0 if brief.get("evidence") else 0.0
    evidence_status = "provided" if evidence else "missing"
    previous: list[str] = []
    queries = []
    opportunities = []
    for candidate in candidates:
        novelty = 1.0 - max(
            (normalized_similarity(candidate.question, item) for item in previous),
            default=0.0,
        )
        novelty = _round(novelty)
        previous.append(candidate.question)
        relevance = _round(0.7 + 0.3 * int(candidate.seed.casefold() in candidate.question.casefold()))
        business_fit = _round(0.5 + 0.25 * bool(brief.get("brand")) + 0.25 * bool(candidate.scenario))
        components = {
            "coverage": 1.0,
            "relevance": relevance,
            "novelty": novelty,
            "evidence": evidence,
            "business_fit": business_fit,
        }
        query_id = _stable_id(
            "qry",
            candidate.generator,
            candidate.intent,
            candidate.question,
            candidate.audience,
            candidate.scenario,
            brief.get("locale", "zh-CN"),
        )
        query = {
            "query_id": query_id,
            "question": candidate.question,
            "intent": candidate.intent,
            "audience": candidate.audience,
            "scenario": candidate.scenario,
            "parent_query_id": candidate.parent_query,
            "rewrites": {
                "standalone": candidate.question,
                "retrieval": f"{candidate.seed} {candidate.audience} {candidate.scenario} {candidate.intent}",
                "evidence": f"{candidate.seed} evidence source methodology {candidate.scenario}",
            },
            "evidence_status": evidence_status,
            "generator": candidate.generator,
            "novelty": novelty,
            "score_components": components,
        }
        total = (
            0.25 * components["coverage"]
            + 0.25 * components["relevance"]
            + 0.20 * components["novelty"]
            + 0.15 * components["evidence"]
            + 0.15 * components["business_fit"]
        )
        opportunities.append(
            {
                "opportunity_id": _stable_id("opp", query_id, ASSET_BY_INTENT[candidate.intent]),
                "query_ids": [query_id],
                "asset_type": ASSET_BY_INTENT[candidate.intent],
                "priority": max(1, min(100, round(total * 100))),
                "rationale": f"{candidate.generator} generated {candidate.intent} intent with decomposed evidence-aware scoring.",
                "evidence_status": evidence_status,
                "score_components": components,
            }
        )
        queries.append(query)
    semantic_payload = {
        "queries": queries,
        "opportunities": opportunities,
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
    query_map = {
        "protocol_version": "1.0.0",
        "run_id": run_id,
        "queries": queries,
        "execution": execution,
        "semantic_digest": semantic_digest,
    }
    opportunity_map = {
        "protocol_version": "1.0.0",
        "run_id": run_id,
        "opportunities": opportunities,
        "semantic_digest": semantic_digest,
    }
    return query_map, opportunity_map, semantic_digest
