from __future__ import annotations

import hashlib
from typing import Any


def _stable_claim_id(text: str, location: str) -> str:
    return f"claim-{hashlib.sha256(f'{location}{chr(31)}{text}'.encode('utf-8')).hexdigest()[:12]}"


def build_claim_map(
    content: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    known_sources = {record["evidence_id"] for record in ledger["records"]}
    claims = []
    for index, claim in enumerate(content["factual_claims"]):
        sources = sorted(set(claim["evidence_ids"]))
        fabricated = sorted(set(sources) - known_sources)
        claims.append(
            {
                "claim_id": claim["claim_id"],
                "text": claim["text"],
                "source_ids": sources,
                "support_status": "supported" if sources and not fabricated else "unsupported",
                "confidence": 1.0 if sources and not fabricated else 0.0,
                "location": f"content.factual_claims[{index}]",
                "repair_action": None if sources and not fabricated else "Attach an approved source or remove the factual assertion.",
            }
        )
    refinement = content["mode_data"].get("refinement")
    if refinement:
        for index, claim in enumerate(refinement["source_claims"]):
            sources = sorted(set(claim["evidence_ids"]))
            supported = bool(sources) and set(sources) <= known_sources
            claims.append(
                {
                    "claim_id": _stable_claim_id(claim["text"], f"refinement[{index}]"),
                    "text": claim["text"],
                    "source_ids": sources,
                    "support_status": "supported" if supported else "unsupported",
                    "confidence": 1.0 if supported else 0.0,
                    "location": f"content.mode_data.refinement.source_claims[{index}]",
                    "repair_action": None if supported else "Attach exact supporting evidence before treating this source claim as verified.",
                }
            )
    supported_count = sum(item["support_status"] == "supported" for item in claims)
    fabricated_citations = sum(
        len(set(item["source_ids"]) - known_sources)
        for item in claims
    )
    return {
        "protocol_version": "1.0.0",
        "run_id": content["run_id"],
        "claims": claims,
        "summary": {
            "claim_count": len(claims),
            "supported_count": supported_count,
            "unsupported_count": len(claims) - supported_count,
            "support_rate": round(supported_count / len(claims), 6) if claims else 1.0,
            "fabricated_citations": fabricated_citations,
        },
    }
