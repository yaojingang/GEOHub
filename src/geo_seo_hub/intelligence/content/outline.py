from __future__ import annotations

from typing import Any


def build_perspective_plan(brief: dict[str, Any]) -> dict[str, Any]:
    audience = brief.get("audience", "general audience")
    return {
        "audience": audience,
        "role": "evidence-bound explainer",
        "decision_questions": [
            f"What does {audience} need to decide about {brief['topic']}?",
            "Which evidence supports the decision?",
        ],
        "counter_questions": [
            "Which claims remain unsupported?",
            "Which constraints or alternatives could change the conclusion?",
        ],
    }


def build_outline(
    content: dict[str, Any],
    claim_map: dict[str, Any],
) -> list[dict[str, Any]]:
    claims = claim_map["claims"]
    sections = []
    for index, section in enumerate(content["sections"]):
        assigned = [claim for position, claim in enumerate(claims) if position % len(content["sections"]) == index]
        sections.append(
            {
                "heading": section["heading"],
                "purpose": section["purpose"],
                "question": f"What evidence-bound answer belongs under {section['heading']}?",
                "claim_ids": [claim["claim_id"] for claim in assigned],
                "source_ids": sorted({source_id for claim in assigned for source_id in claim["source_ids"]}),
            }
        )
    return sections
