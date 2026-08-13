import json
import hashlib
from pathlib import Path

from geo_seo_hub.quality.observability import aggregate_adoption_drift


def _write_lineage(run: Path, skill_id: str, status: str, error_class=None):
    run.mkdir(parents=True)
    digest = hashlib.sha256(run.name.encode("utf-8")).hexdigest()[:16]
    (run / "run-lineage.json").write_text(
        json.dumps(
            {
                "protocol_version": "1.0.0",
                "trace_id": f"trace-{digest}",
                "run_id": run.name,
                "skill_id": skill_id,
                "data_class": "L0",
                "events": [
                    {
                        "span_id": f"span-{digest}",
                        "parent_span_id": None,
                        "stage": "execute",
                        "status": status,
                        "duration_ms": 0,
                        "artifact_hashes": {},
                        "metric_names": [],
                        "token_count": 0,
                        "cost_usd": 0.0,
                        "error_class": error_class,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_adoption_drift_aggregation_keeps_only_allowlisted_metadata(tmp_path):
    _write_lineage(tmp_path / "run-1", "geo-discover", "completed")
    _write_lineage(tmp_path / "run-2", "geo-discover", "failed", "input-validation")
    _write_lineage(tmp_path / "run-3", "geo-measure", "completed-with-warnings")

    report = aggregate_adoption_drift(tmp_path)

    assert report["run_count"] == 3
    assert report["by_skill"] == {"geo-discover": 2, "geo-measure": 1}
    assert report["by_status"] == {"completed": 1, "completed-with-warnings": 1, "failed": 1}
    assert report["errors"] == {"input-validation": 1}
    assert set(report) == {"protocol_version", "run_count", "by_skill", "by_status", "errors", "gaps"}
