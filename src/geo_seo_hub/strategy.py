from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .artifact_bus import ArtifactBus
from .intelligence.optimization import build_strategy_artifacts
from .quality.lineage import build_run_lineage
from .validation import load_bounded_json, validate_artifact
from .version import package_version


Clock = Callable[[], datetime]


def _validate_request(request: dict) -> None:
    if not isinstance(request, dict):
        raise ValueError("strategy request must be a JSON object")
    required = {
        "protocol_version", "subject", "goals", "audience", "constraints", "risks", "brand_rules",
        "metric_weights", "baseline", "diagnosis_actions", "evidence_ids", "observation_window_days",
    }
    missing = sorted(required - set(request))
    if missing:
        raise ValueError(f"strategy request missing fields: {missing}")
    if request["protocol_version"] != "1.0.0":
        raise ValueError("unsupported strategy request protocol")
    if not isinstance(request["subject"], str) or not request["subject"].strip():
        raise ValueError("strategy subject must be non-blank")
    for field in ("goals", "audience", "constraints", "risks", "brand_rules", "diagnosis_actions", "evidence_ids"):
        value = request[field]
        if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError(f"strategy {field} must be a non-empty string list")
    weights = request["metric_weights"]
    if (
        not isinstance(weights, dict)
        or not weights
        or any(not isinstance(key, str) or not key.strip() for key in weights)
        or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0 for value in weights.values())
        or abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-9
    ):
        raise ValueError("strategy metric weights must be non-negative and sum to 1")
    baseline = request["baseline"]
    if not isinstance(baseline, dict) or set(baseline) != {"semantic_digest", "query_panel", "metrics"}:
        raise ValueError("strategy baseline fields are invalid")
    if not isinstance(baseline["semantic_digest"], str) or re.fullmatch(r"[0-9a-f]{64}", baseline["semantic_digest"]) is None:
        raise ValueError("strategy baseline requires a semantic SHA-256 digest")
    panel = baseline["query_panel"]
    if not isinstance(panel, list) or not panel or any(not isinstance(item, str) or not item.strip() for item in panel) or len(panel) != len(set(panel)):
        raise ValueError("strategy baseline requires a query panel")
    metrics = baseline["metrics"]
    if not isinstance(metrics, dict) or not metrics or any(not isinstance(key, str) or not key.strip() for key in metrics) or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in metrics.values()):
        raise ValueError("strategy baseline metrics must be finite numbers")
    if set(weights) != set(metrics):
        raise ValueError("strategy metric weights must match baseline metrics")
    window = request["observation_window_days"]
    if isinstance(window, bool) or not isinstance(window, int) or not 1 <= window <= 365:
        raise ValueError("observation_window_days must be between 1 and 365")


def strategy(input_path: Path, output_path: Path, *, clock: Clock | None = None) -> dict:
    request = load_bounded_json(input_path, max_bytes=4 * 1024 * 1024, field="strategy request")
    _validate_request(request)
    canonical = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    run_id = f"run-strategy-{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    artifacts = build_strategy_artifacts(request, run_id)
    validate_artifact("strategy-candidates", artifacts["candidate_set"])
    validate_artifact("fidelity-report", artifacts["fidelity"])
    validate_artifact("experiment-plan", artifacts["experiment"])
    validate_artifact("strategy-memory", artifacts["memory"])
    validate_artifact("publication-handoff", artifacts["handoff"])
    warning = "real publication and post-publication measurement are missing evidence"
    quality = {
        "protocol_version": "1.0.0", "run_id": run_id,
        "passed_checks": ["bounded candidate set", "fidelity checks recorded", "offline approval boundary enforced", "positive-only memory policy enforced"],
        "warnings": [warning], "failed_checks": [], "status": "passed-with-warnings",
    }
    validate_artifact("quality-report", quality)
    staged = [
        "input/strategy-request.json", "strategy-candidates.json", "fidelity-report.json", "experiment-plan.json",
        "publication-handoff.json", "strategy-memory.json", "quality-report.json",
    ]
    declared = [*staged, "run-lineage.json"]
    manifest = {
        "protocol_version": "1.0.0", "run_id": run_id, "created_at": created_at,
        "generator": {"name": "geo-seo-hub-strategy", "version": package_version()},
        "input_artifact": "input/strategy-request.json", "artifacts": declared, "status": "completed-with-warnings",
    }
    validate_artifact("run-manifest", manifest)
    run_path = output_path / run_id
    with ArtifactBus.transaction(output_path, run_id) as bus:
        bus.write_json(staged[0], request)
        bus.write_json(staged[1], artifacts["candidate_set"], "strategy-candidates")
        bus.write_json(staged[2], artifacts["fidelity"], "fidelity-report")
        bus.write_json(staged[3], artifacts["experiment"], "experiment-plan")
        bus.write_json(staged[4], artifacts["handoff"], "publication-handoff")
        bus.write_json(staged[5], artifacts["memory"], "strategy-memory")
        bus.write_json(staged[6], quality, "quality-report")
        lineage = build_run_lineage(bus.root, run_id=run_id, skill_id="geo-strategy", status=manifest["status"], artifact_paths=staged, metric_names=tuple(sorted(request["metric_weights"])))
        bus.write_json("run-lineage.json", lineage, "run-lineage")
        bus.write_json("run-manifest.json", manifest, "run-manifest")
        bus.publish(set(declared) | {"run-manifest.json"})
    return {"run_id": run_id, "status": "completed", "artifact_status": manifest["status"], "output": str(run_path.resolve()), "candidate_count": len(artifacts["candidate_set"]["candidates"]), "external_evidence_status": "missing evidence"}
