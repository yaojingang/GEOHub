from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


SHADOW_THRESHOLD = 0.55
SHADOW_THRESHOLD_VERSION = "semantic-shadow-1.0.0"


class SemanticScorer(Protocol):
    model_id: str

    def score(self, text: str, candidate_skill_ids: Sequence[str]) -> Mapping[str, float]: ...


@dataclass(frozen=True)
class StaticSemanticScorer:
    scores: Mapping[str, float]
    model_id: str = "static-fixture-v1"

    def score(self, _text: str, candidate_skill_ids: Sequence[str]) -> Mapping[str, float]:
        return {
            skill_id: self.scores.get(skill_id, 0.0)
            for skill_id in candidate_skill_ids
        }


def build_shadow_assessment(
    text: str,
    registry: dict[str, Any],
    production: dict[str, Any],
    scorer: SemanticScorer,
    *,
    threshold: float = SHADOW_THRESHOLD,
) -> dict[str, Any]:
    """Score a route in shadow mode while preserving the lexical decision."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("semantic threshold must be between zero and one")
    identifiers = [skill["id"] for skill in registry["skills"]]
    raw = scorer.score(text, identifiers)
    unknown = sorted(set(raw) - set(identifiers))
    if unknown:
        raise ValueError(f"semantic scorer returned unknown Skill IDs: {unknown}")
    candidates = []
    for index, skill in enumerate(registry["skills"]):
        value = raw.get(skill["id"], 0.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"semantic score is invalid for {skill['id']}")
        score = float(value)
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"semantic score is outside [0, 1] for {skill['id']}")
        eligible = skill["status"] == "active" and bool(skill["entry"])
        candidates.append(
            {
                "skill_id": skill["id"],
                "status": skill["status"],
                "eligible": eligible,
                "score_components": {"semantic": score},
                "total_score": score,
                "registry_order": index,
            }
        )
    ranked = sorted(
        (item for item in candidates if item["eligible"] and item["total_score"] >= threshold),
        key=lambda item: (-item["total_score"], item["registry_order"]),
    )
    shadow_skill_id = ranked[0]["skill_id"] if ranked else None
    disagreed = shadow_skill_id is not None and shadow_skill_id != production["skill_id"]
    if shadow_skill_id is None:
        reason = "No eligible active candidate met the semantic threshold."
    elif disagreed:
        reason = (
            f"Shadow candidate {shadow_skill_id} differs from lexical production route "
            f"{production['skill_id']}; production remains unchanged."
        )
    else:
        reason = f"Shadow candidate agrees with lexical production route {production['skill_id']}."
    return {
        "mode": "shadow",
        "threshold": threshold,
        "threshold_version": SHADOW_THRESHOLD_VERSION,
        "model_id": scorer.model_id,
        "production_skill_id": production["skill_id"],
        "shadow_skill_id": shadow_skill_id,
        "disagreed": disagreed,
        "decision_reason": reason,
        "candidates": candidates,
    }
