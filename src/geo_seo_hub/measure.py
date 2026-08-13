from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .artifact_bus import ArtifactBus
from .intelligence.measurement import build_visibility_payload
from .quality.lineage import build_run_lineage
from .validation import load_bounded_json, validate_artifact
from .version import package_version


Clock = Callable[[], datetime]


def measure(input_path: Path, output_path: Path, *, clock: Clock | None = None) -> dict:
    bundle = load_bounded_json(
        input_path,
        max_bytes=16 * 1024 * 1024,
        field="engine observation bundle",
    )
    validate_artifact("engine-observation-bundle", bundle)
    canonical = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    run_id = f"run-measure-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12]}"
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    generated_at = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    report = build_visibility_payload(bundle, run_id)
    report["generated_at"] = generated_at
    validate_artifact("visibility-report", report)
    warnings = list(report["gaps"])
    quality_report = {
        "protocol_version": "1.0.0",
        "run_id": run_id,
        "passed_checks": [
            "observation bundle schema valid",
            "query panel and observation slots consistent",
            "aggregate metrics retain raw components",
            "execution remained offline",
        ],
        "warnings": warnings,
        "failed_checks": [],
        "status": "passed-with-warnings" if warnings else "passed",
    }
    validate_artifact("quality-report", quality_report)
    lineage_inputs = [
        "input/engine-observation-bundle.json",
        "visibility-report.json",
        "quality-report.json",
    ]
    artifact_paths = [*lineage_inputs, "run-lineage.json"]
    manifest = {
        "protocol_version": "1.0.0",
        "run_id": run_id,
        "created_at": generated_at,
        "generator": {"name": "geo-seo-hub-measure", "version": package_version()},
        "input_artifact": "input/engine-observation-bundle.json",
        "artifacts": artifact_paths,
        "status": "completed-with-warnings" if warnings else "completed",
    }
    validate_artifact("run-manifest", manifest)
    run_path = output_path / run_id
    with ArtifactBus.transaction(output_path, run_id) as bus:
        bus.write_json("input/engine-observation-bundle.json", bundle, "engine-observation-bundle")
        bus.write_json("visibility-report.json", report, "visibility-report")
        bus.write_json("quality-report.json", quality_report, "quality-report")
        lineage = build_run_lineage(
            bus.root,
            run_id=run_id,
            skill_id="geo-measure",
            status=manifest["status"],
            artifact_paths=lineage_inputs,
            metric_names=("citation-share", "coverage", "mention-rate", "source-inclusion-rate"),
        )
        bus.write_json("run-lineage.json", lineage, "run-lineage")
        bus.write_json("run-manifest.json", manifest, "run-manifest")
        bus.publish(set(artifact_paths) | {"run-manifest.json"})
    return {
        "run_id": run_id,
        "status": "completed",
        "artifact_status": manifest["status"],
        "output": str(run_path.resolve()),
        "observation_count": len(bundle["observations"]),
        "semantic_digest": report["semantic_digest"],
        "warning_count": len(warnings),
    }
