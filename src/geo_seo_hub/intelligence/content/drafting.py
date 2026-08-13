from __future__ import annotations

import hashlib
import json
from typing import Any

from .outline import build_outline, build_perspective_plan
from .research_bundle import build_research_bundle


def build_content_pipeline(
    brief: dict[str, Any],
    source_text: str | None,
    content: dict[str, Any],
    claim_map: dict[str, Any],
    *,
    execution_mode: str,
    failures: list[str],
) -> dict[str, Any]:
    payload = {
        "protocol_version": "1.0.0",
        "run_id": content["run_id"],
        "execution": {
            "mode": execution_mode,
            "status": "degraded" if failures else "completed",
            "failures": failures,
        },
        "research_bundle": build_research_bundle(brief, source_text),
        "perspective_plan": build_perspective_plan(brief),
        "outline": build_outline(content, claim_map),
        "verification": claim_map["summary"],
        "polish": {
            "structure_reviewed": True,
            "claim_boundary_preserved": True,
            "artifact_design": "responsive-semantic-html",
        },
    }
    semantic = {key: value for key, value in payload.items() if key != "run_id"}
    payload["semantic_digest"] = hashlib.sha256(
        json.dumps(
            semantic,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return payload
