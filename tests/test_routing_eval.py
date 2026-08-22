from __future__ import annotations

from geo_seo_hub.quality.routing_eval import evaluate_routing_cases


def test_routing_evaluator_reports_independent_quality_axes():
    cases = [
        {
            "id": "one",
            "category": "single-intent",
            "text": "discover",
            "expected": {"decision_type": "single_skill", "skill_id": "geo-discover", "workflow_id": None},
        },
        {
            "id": "two",
            "category": "out-of-domain",
            "text": "weather",
            "expected": {"decision_type": "abstain", "skill_id": None, "workflow_id": None},
        },
    ]

    def oracle(text: str):
        if text == "discover":
            return {
                "skill_id": "geo-discover",
                "runnable": True,
                "decision": {"type": "single_skill"},
            }
        return {
            "skill_id": "geo",
            "runnable": False,
            "decision": {"type": "abstain"},
        }

    result = evaluate_routing_cases(cases, oracle)
    assert result["macro_skill_f1"] == 1.0
    assert result["decision_recall"] == {"abstain": 1.0, "single_skill": 1.0}
    assert result["ood_false_runnable_rate"] == 0.0
    assert result["accepted_route_error_rate"] == 0.0
    assert result["coverage"] == 0.5
