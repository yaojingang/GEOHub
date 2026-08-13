from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .artifact_bus import ArtifactBus
from .intelligence.measurement import build_visibility_payload
from .quality.lineage import build_run_lineage
from .validation import load_bounded_json, normalize_artifact_uri, validate_artifact
from .version import package_version


Clock = Callable[[], datetime]


def _legacy_bundle(brief: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    """Translate the 0.3 measurement brief into the governed observation protocol."""
    validate_artifact("measurement-brief", brief)
    trial_ids = [item["trial_id"] for item in brief["observations"]]
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("measurement brief contains duplicate trial_id values")

    normalized_uris = [
        normalize_artifact_uri(item["source_uri"], field=f"observations[{index}].source_uri")
        for index, item in enumerate(brief["observations"])
    ]
    queries: dict[str, dict[str, str]] = {}
    slot_repetitions: dict[tuple[str, str, str], int] = {}
    observations = []
    for index, (source, source_uri) in enumerate(zip(brief["observations"], normalized_uris, strict=True)):
        query_id = source["query_id"].strip()
        queries.setdefault(
            query_id,
            {"query_id": query_id, "query_text": query_id, "intent": "evaluate"},
        )
        timepoint = source["collected_at"].strip()
        slot = (source["engine"].strip(), timepoint, query_id)
        repetition = slot_repetitions.get(slot, 0) + 1
        slot_repetitions[slot] = repetition
        parsed = urlsplit(source_uri)
        citations = (
            [{"uri": source_uri, "position": 1}]
            if source["cited"] is True and parsed.scheme.casefold() in {"http", "https"}
            else []
        )
        observations.append(
            {
                "observation_id": f"legacy-{hashlib.sha256((source['trial_id'] + source_uri).encode()).hexdigest()[:24]}",
                "engine": source["engine"].strip(),
                "model": source["model_version"].strip(),
                "query_id": query_id,
                "query_text": query_id,
                "answer_text": brief["subject"].strip() if source["answered"] else "",
                "citations": citations,
                "observed_at": timepoint,
                "locale": source["language"].strip(),
                "session_policy": "recorded-session",
                "panel_version": "legacy-0.3",
                "collection_method": "recorded_fixture",
                "timepoint": timepoint,
                "repetition": repetition,
            }
        )
    target_source_uris = sorted(
        {
            uri
            for uri in normalized_uris
            if urlsplit(uri).scheme.casefold() in {"http", "https"}
        }
    )
    bundle = {
        "protocol_version": "1.0.0",
        "bundle_id": f"legacy-{hashlib.sha256(brief['measurement_id'].encode()).hexdigest()[:16]}",
        "subject": {
            "name": brief["subject"].strip(),
            "aliases": [brief["subject"].strip()],
            "target_source_uris": target_source_uris,
        },
        "panel": {
            "panel_version": "legacy-0.3",
            "queries": [queries[key] for key in sorted(queries)],
            "expected_engines": sorted({item["engine"] for item in observations}),
            "expected_timepoints": sorted({item["timepoint"] for item in observations}),
            "expected_repetitions": max(slot_repetitions.values()),
        },
        "collection": {
            "collector": "geo-seo-hub-legacy-adapter",
            "permission_scope": "user-provided-observations",
            "source_note": "Translated from the 0.3 measurement brief protocol",
        },
        "observations": observations,
    }
    return bundle, {
        "trial_count": len(brief["observations"]),
        "eligible_trial_count": sum(item["eligible"] for item in brief["observations"]),
    }


def measure(input_path: Path, output_path: Path, *, clock: Clock | None = None) -> dict:
    source = load_bounded_json(
        input_path,
        max_bytes=16 * 1024 * 1024,
        field="engine observation bundle",
    )
    legacy_summary: dict[str, int] = {}
    if "measurement_id" in source:
        bundle, legacy_summary = _legacy_bundle(source)
    else:
        bundle = source
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
        **legacy_summary,
    }
