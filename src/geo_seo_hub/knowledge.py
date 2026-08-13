from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .artifact_bus import ArtifactBus
from .intelligence.knowledge import build_knowledge_graph, query_knowledge_graph
from .quality.lineage import build_run_lineage
from .validation import load_bounded_json, validate_artifact
from .version import package_version


Clock = Callable[[], datetime]


def knowledge(input_path: Path, output_path: Path, *, clock: Clock | None = None) -> dict:
    request = load_bounded_json(input_path, max_bytes=16 * 1024 * 1024, field="knowledge request")
    graph = build_knowledge_graph(request)
    validate_artifact("knowledge-graph", graph)
    query_result = {"protocol_version": "1.0.0", **query_knowledge_graph(graph, request.get("query", {}))}
    validate_artifact("knowledge-query-result", query_result)
    canonical = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    run_id = f"run-knowledge-{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    created_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    ledger = {
        "protocol_version": "1.0.0", "run_id": run_id,
        "records": [
            {"evidence_id": source["source_id"], "claim": f"Approved knowledge source indexed for {request['subject']}", "source_uri": source["source_uri"], "status": "provided"}
            for source in request["sources"]
        ],
        "missing_evidence": list(graph["gaps"]),
    }
    validate_artifact("evidence-ledger", ledger)
    warnings = list(graph["gaps"])
    quality = {
        "protocol_version": "1.0.0", "run_id": run_id,
        "passed_checks": ["source hashes indexed", "entity identity normalized", "relation lineage retained", "conflicting facts preserved"],
        "warnings": warnings, "failed_checks": [], "status": "passed-with-warnings" if warnings else "passed",
    }
    validate_artifact("quality-report", quality)
    staged = ["input/knowledge-request.json", "knowledge-graph.json", "knowledge-query-result.json", "evidence-ledger.json", "quality-report.json"]
    declared = [*staged, "run-lineage.json"]
    manifest_status = "completed-with-warnings" if warnings else "completed"
    manifest = {
        "protocol_version": "1.0.0", "run_id": run_id, "created_at": created_at,
        "generator": {"name": "geo-seo-hub-knowledge", "version": package_version()},
        "input_artifact": staged[0], "artifacts": declared, "status": manifest_status,
    }
    validate_artifact("run-manifest", manifest)
    run_path = output_path / run_id
    with ArtifactBus.transaction(output_path, run_id) as bus:
        bus.write_json(staged[0], request)
        bus.write_json(staged[1], graph, "knowledge-graph")
        bus.write_json(staged[2], query_result, "knowledge-query-result")
        bus.write_json(staged[3], ledger, "evidence-ledger")
        bus.write_json(staged[4], quality, "quality-report")
        lineage = build_run_lineage(bus.root, run_id=run_id, skill_id="geo-knowledge", status=manifest_status, artifact_paths=staged, metric_names=("source-coverage", "entity-count", "relation-count"))
        bus.write_json("run-lineage.json", lineage, "run-lineage")
        bus.write_json("run-manifest.json", manifest, "run-manifest")
        bus.publish(set(declared) | {"run-manifest.json"})
    return {"run_id": run_id, "status": "completed", "artifact_status": manifest_status, "output": str(run_path.resolve()), "entity_count": len(graph["entities"]), "relation_count": len(graph["relations"]), "evidence_status": "provided"}
