from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Iterable


RouteCallable = Callable[[str], dict[str, Any]]


def _f1(tp: int, fp: int, fn: int) -> float:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def evaluate_routing_cases(
    cases: Iterable[dict[str, Any]],
    route_request: RouteCallable,
) -> dict[str, Any]:
    """Evaluate decision, abstention, workflow, and accepted-route quality separately."""
    rows: list[dict[str, Any]] = []
    skill_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    decision_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    accepted = accepted_errors = ood_total = ood_false_runnable = workflow_total = workflow_exact = 0

    for case in cases:
        expected = case["expected"]
        actual = route_request(case["text"])
        actual_decision = actual["decision"]["type"]
        actual_skill = actual.get("skill_id") if actual_decision in {"single_skill", "workflow", "unavailable"} else None
        actual_workflow = (actual.get("workflow") or {}).get("id")
        expected_decision = expected["decision_type"]
        expected_skill = expected.get("skill_id")
        expected_workflow = expected.get("workflow_id")

        for label in set(filter(None, (expected_skill, actual_skill))):
            counts = skill_counts[label]
            counts["tp" if expected_skill == actual_skill == label else "fn" if expected_skill == label else "fp"] += 1
        for label in {expected_decision, actual_decision}:
            counts = decision_counts[label]
            counts["tp" if expected_decision == actual_decision == label else "fn" if expected_decision == label else "fp"] += 1

        if actual.get("runnable"):
            accepted += 1
            accepted_errors += int(
                expected_decision not in {"single_skill", "workflow"}
                or actual_skill != expected_skill
                or actual_workflow != expected_workflow
            )
        if case["category"] == "out-of-domain":
            ood_total += 1
            ood_false_runnable += int(bool(actual.get("runnable")))
        if expected_workflow:
            workflow_total += 1
            workflow_exact += int(actual_workflow == expected_workflow and actual_decision == expected_decision)

        rows.append(
            {
                "id": case["id"],
                "expected": expected,
                "actual": {
                    "decision_type": actual_decision,
                    "skill_id": actual_skill,
                    "workflow_id": actual_workflow,
                    "runnable": bool(actual.get("runnable")),
                },
                "passed": (
                    actual_decision == expected_decision
                    and actual_skill == expected_skill
                    and actual_workflow == expected_workflow
                ),
            }
        )

    skill_f1 = {
        label: _f1(**counts) for label, counts in sorted(skill_counts.items())
    }
    decision_recall = {
        label: counts["tp"] / (counts["tp"] + counts["fn"])
        if counts["tp"] + counts["fn"]
        else 0.0
        for label, counts in sorted(decision_counts.items())
    }
    return {
        "case_count": len(rows),
        "macro_skill_f1": sum(skill_f1.values()) / len(skill_f1) if skill_f1 else 0.0,
        "per_skill_f1": skill_f1,
        "decision_recall": decision_recall,
        "ood_false_runnable_rate": ood_false_runnable / ood_total if ood_total else 0.0,
        "workflow_exact_match": workflow_exact / workflow_total if workflow_total else 0.0,
        "accepted_route_error_rate": accepted_errors / accepted if accepted else 0.0,
        "coverage": accepted / len(rows) if rows else 0.0,
        "results": rows,
    }
