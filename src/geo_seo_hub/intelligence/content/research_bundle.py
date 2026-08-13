from __future__ import annotations

import hashlib
from typing import Any


def build_research_bundle(
    brief: dict[str, Any],
    source_text: str | None,
) -> dict[str, Any]:
    evidence = [
        {
            "source_id": item["label"],
            "claim": item["claim"],
            "source_uri": item["source_uri"],
            "entity": item.get("entity"),
        }
        for item in brief.get("evidence", [])
    ]
    source_snapshot = None
    if source_text is not None:
        source_snapshot = {
            "sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "claim_count_hint": len([line for line in source_text.splitlines() if line.strip()]),
        }
    return {
        "topic": brief["topic"],
        "audience": brief.get("audience", "general audience"),
        "evidence": evidence,
        "source_snapshot": source_snapshot,
        "evidence_gaps": [] if evidence else ["No approved factual evidence was supplied."],
    }
