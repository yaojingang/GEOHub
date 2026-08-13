from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from ..validation import validate_artifact


def _digest(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_strategy_candidates(request: dict[str, Any]) -> list[dict[str, Any]]:
    actions = [str(item).strip() for item in request.get("diagnosis_actions", []) if str(item).strip()]
    if not actions:
        actions = ["close the highest-confidence evidence gap", "improve source-linked answer coverage"]
    candidates = []
    for index, action in enumerate(actions[:4], 1):
        proposal = {
            "candidate_id": f"candidate-{index}",
            "action_diff": [action],
            "expected_impact": {
                metric: round(weight * (0.04 + index * 0.01), 6)
                for metric, weight in sorted(request.get("metric_weights", {}).items())
            },
            "evidence_ids": sorted(set(request.get("evidence_ids", []))),
            "status": "offline-proposed",
        }
        checks = {
            "constraints_covered": bool(request.get("constraints")),
            "brand_rules_covered": bool(request.get("brand_rules")),
            "evidence_linked": bool(proposal["evidence_ids"]),
            "risk_register_present": bool(request.get("risks")),
        }
        proposal["fidelity"] = {"passed": all(checks.values()), "checks": checks}
        proposal["semantic_digest"] = _digest(proposal)
        candidates.append(proposal)
    while len(candidates) < 2:
        index = len(candidates) + 1
        proposal = {
            "candidate_id": f"candidate-{index}",
            "action_diff": ["expand approved source coverage"],
            "expected_impact": {metric: round(weight * 0.03, 6) for metric, weight in sorted(request.get("metric_weights", {}).items())},
            "evidence_ids": sorted(set(request.get("evidence_ids", []))),
            "status": "offline-proposed",
            "fidelity": {"passed": True, "checks": {"bounded_fallback": True}},
        }
        proposal["semantic_digest"] = _digest(proposal)
        candidates.append(proposal)
    return candidates


def promote_strategy_memory(
    memory: dict[str, Any],
    candidate: dict[str, Any],
    *,
    fidelity_report: dict[str, Any],
    experiment_plan: dict[str, Any],
    publication_handoff: dict[str, Any],
    publication_receipt: dict[str, Any],
    visibility_report: dict[str, Any],
) -> bool:
    if not isinstance(memory, dict) or not isinstance(candidate, dict):
        raise ValueError("strategy memory and candidate must be objects")
    validate_artifact("strategy-memory", memory)
    validate_artifact("fidelity-report", fidelity_report)
    validate_artifact("experiment-plan", experiment_plan)
    validate_artifact("publication-handoff", publication_handoff)
    validate_artifact("publication-receipt", publication_receipt)
    validate_artifact("visibility-report", visibility_report)
    current_memory_digest = _digest({key: value for key, value in memory.items() if key != "semantic_digest"})
    if memory["semantic_digest"] != current_memory_digest:
        raise ValueError("strategy memory semantic digest mismatch")
    candidate_digest = candidate.get("semantic_digest")
    if (
        not isinstance(candidate.get("candidate_id"), str)
        or re.fullmatch(r"[0-9a-f]{64}", str(candidate_digest or "")) is None
        or candidate_digest != _digest({key: value for key, value in candidate.items() if key != "semantic_digest"})
    ):
        raise ValueError("strategy candidate semantic digest mismatch")
    receipt_digest = _digest({key: value for key, value in publication_receipt.items() if key != "semantic_digest"})
    if publication_receipt["semantic_digest"] != receipt_digest:
        raise ValueError("publication receipt semantic digest mismatch")
    visibility_semantic = {
        key: visibility_report[key]
        for key in ("bundle_id", "panel_version", "query_panel", "metrics", "by_engine", "query_components", "gaps")
    }
    if visibility_report["semantic_digest"] != _digest(visibility_semantic):
        raise ValueError("visibility report semantic digest mismatch")
    handoff_digest = _digest(publication_handoff)
    candidate_id = candidate["candidate_id"]
    if (
        not fidelity_report["passed"]
        or fidelity_report["selected_candidate_id"] != candidate_id
        or experiment_plan["candidate_id"] != candidate_id
        or publication_handoff["candidate_digest"] != candidate_digest
        or publication_receipt["candidate_digest"] != candidate_digest
        or publication_receipt["handoff_digest"] != handoff_digest
        or publication_handoff["baseline_digest"] != experiment_plan["baseline"]["semantic_digest"]
        or publication_handoff["observation_window"]["days"] != experiment_plan["observation_window_days"]
        or candidate_id not in memory["pending_candidates"]
    ):
        raise ValueError("strategy promotion artifacts are not bound to one approved candidate")
    if visibility_report["query_panel"] != experiment_plan["baseline"]["query_panel"]:
        raise ValueError("strategy promotion requires an unchanged query panel")
    published_at = datetime.fromisoformat(publication_receipt["published_at"].replace("Z", "+00:00"))
    observed_at = datetime.fromisoformat(visibility_report["generated_at"].replace("Z", "+00:00"))
    elapsed_days = (observed_at.astimezone(timezone.utc) - published_at.astimezone(timezone.utc)).total_seconds() / 86400
    if elapsed_days < publication_handoff["observation_window"]["days"]:
        raise ValueError("strategy observation window has not elapsed")
    baseline_metrics = experiment_plan["baseline"]["metrics"]
    weights = experiment_plan["metric_weights"]
    if set(weights) != set(baseline_metrics) or not set(weights) <= set(visibility_report["metrics"]):
        raise ValueError("strategy promotion metrics do not match the experiment plan")
    metric_delta = math.fsum(
        weights[name] * (visibility_report["metrics"][name]["value"] - baseline_metrics[name])
        for name in weights
    )
    if not math.isfinite(metric_delta):
        raise ValueError("strategy promotion metric delta is invalid")
    records = memory.setdefault("records", [])
    if not isinstance(records, list):
        raise ValueError("strategy memory records must be a list")
    if any(record.get("candidate_id") == candidate_id for record in records if isinstance(record, dict)):
        return False
    promoted = metric_delta > 0
    if promoted:
        records.append(
            {
                "candidate_id": candidate_id,
                "candidate_digest": candidate_digest,
                "fidelity_passed": True,
                "metric_delta": round(float(metric_delta), 8),
                "promotion": "promoted",
            }
        )
    memory["pending_candidates"] = [item for item in memory["pending_candidates"] if item != candidate_id]
    memory["status"] = "observation-complete"
    memory["early_stop"] = early_stop([float(metric_delta)])
    memory["semantic_digest"] = _digest({key: value for key, value in memory.items() if key != "semantic_digest"})
    validate_artifact("strategy-memory", memory)
    return promoted


def early_stop(metric_deltas: list[float], *, max_no_improvement: int = 2) -> dict[str, Any]:
    if max_no_improvement < 1:
        raise ValueError("max_no_improvement must be positive")
    consecutive = 0
    for delta in reversed(metric_deltas):
        if delta > 0:
            break
        consecutive += 1
    stop = consecutive >= max_no_improvement
    return {
        "stop": stop,
        "reason": "consecutive observations without positive improvement" if stop else None,
        "consecutive_no_improvement": consecutive,
    }


def build_strategy_artifacts(request: dict[str, Any], run_id: str) -> dict[str, Any]:
    candidates = build_strategy_candidates(request)
    approved = next((item for item in candidates if item["fidelity"]["passed"]), candidates[0])
    candidate_set = {"protocol_version": "1.0.0", "run_id": run_id, "candidates": candidates}
    fidelity = {
        "protocol_version": "1.0.0",
        "run_id": run_id,
        "selected_candidate_id": approved["candidate_id"],
        "passed": approved["fidelity"]["passed"],
        "checks": deepcopy(approved["fidelity"]["checks"]),
        "external_validation": "missing evidence",
    }
    experiment = {
        "protocol_version": "1.0.0",
        "run_id": run_id,
        "candidate_id": approved["candidate_id"],
        "baseline": deepcopy(request["baseline"]),
        "metric_weights": deepcopy(request["metric_weights"]),
        "observation_window_days": request["observation_window_days"],
        "success_rule": "weighted metric delta must be greater than zero after verified publication",
        "early_stop": {"max_consecutive_no_improvement": 2, "fidelity_failure_stops": True},
    }
    handoff = {
        "protocol_version": "1.0.0",
        "run_id": run_id,
        "candidate_digest": approved["semantic_digest"],
        "deployment_requirements": ["human approval", "verified publication receipt", "unchanged query panel"],
        "observation_window": {"days": request["observation_window_days"], "starts_after": "verified external publication"},
        "query_panel": request["baseline"]["query_panel"],
        "status": "awaiting_external_publication",
        "baseline_digest": request["baseline"]["semantic_digest"],
    }
    context_signature = _digest(
        {key: request.get(key) for key in ("subject", "goals", "audience", "constraints", "risks", "brand_rules")}
    )
    memory_base = {
        "protocol_version": "1.0.0",
        "run_id": run_id,
        "context_signature": context_signature,
        "status": "offline-approved",
        "records": [],
        "pending_candidates": [approved["candidate_id"]],
        "early_stop": early_stop([]),
    }
    memory_base["semantic_digest"] = _digest(memory_base)
    return {
        "candidate_set": candidate_set,
        "fidelity": fidelity,
        "experiment": experiment,
        "handoff": handoff,
        "memory": memory_base,
    }
