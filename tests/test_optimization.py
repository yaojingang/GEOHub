import json
from datetime import datetime, timezone
from pathlib import Path

from geo_seo_hub.intelligence.optimization import build_strategy_artifacts
from geo_seo_hub.intelligence.optimization import early_stop, promote_strategy_memory
from geo_seo_hub.strategy import strategy
from geo_seo_hub.validation import validate_artifact


FIXTURE = Path(__file__).parent / "fixtures" / "strategy-request.json"


def test_strategy_builds_bounded_candidates_and_external_handoff(tmp_path):
    result = strategy(
        FIXTURE,
        tmp_path / "runs",
        clock=lambda: datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    run = Path(result["output"])
    candidates = json.loads((run / "strategy-candidates.json").read_text())
    memory = json.loads((run / "strategy-memory.json").read_text())
    handoff = json.loads((run / "publication-handoff.json").read_text())
    validate_artifact("strategy-memory", memory)
    validate_artifact("publication-handoff", handoff)
    assert 2 <= len(candidates["candidates"]) <= 4
    assert all(item["fidelity"]["passed"] for item in candidates["candidates"])
    assert handoff["status"] == "awaiting_external_publication"
    assert memory["status"] == "offline-approved"
    assert memory["records"] == []
    assert result["external_evidence_status"] == "missing evidence"
    assert (run / "run-lineage.json").is_file()


def test_strategy_memory_promotes_only_positive_fidelity_checked_observations():
    request = json.loads(FIXTURE.read_text())
    artifacts = build_strategy_artifacts(request, "run-strategy-promotion")
    candidate = artifacts["candidate_set"]["candidates"][0]
    receipt = {
        "protocol_version": "1.0.0",
        "publication_id": "publication-1",
        "candidate_digest": candidate["semantic_digest"],
        "handoff_digest": "",
        "target_uri": "https://example.invalid/publication",
        "published_at": "2026-08-01T00:00:00Z",
        "status": "verified",
    }

    def digest(payload):
        import hashlib

        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    receipt["handoff_digest"] = digest(artifacts["handoff"])
    receipt["semantic_digest"] = digest(receipt)
    metrics = {
        name: {"value": value + 0.1, "numerator": value + 0.1, "denominator": 1, "missing_count": 0}
        for name, value in request["baseline"]["metrics"].items()
    }
    for name in ("position_weighted_visibility", "answer_coverage", "observation_coverage", "missing_observation_rate"):
        metrics[name] = {"value": 0.0, "numerator": 0.0, "denominator": 1, "missing_count": 0}
    visibility = {
        "protocol_version": "1.0.0",
        "run_id": "run-measure-promotion",
        "bundle_id": "bundle-promotion",
        "panel_version": "panel-promotion",
        "query_panel": request["baseline"]["query_panel"],
        "generated_at": "2026-09-01T00:00:00Z",
        "metrics": metrics,
        "by_engine": {},
        "query_components": [],
        "gaps": [],
    }
    visibility["semantic_digest"] = digest(
        {key: visibility[key] for key in ("bundle_id", "panel_version", "query_panel", "metrics", "by_engine", "query_components", "gaps")}
    )
    memory = artifacts["memory"]
    assert promote_strategy_memory(
        memory,
        candidate,
        fidelity_report=artifacts["fidelity"],
        experiment_plan=artifacts["experiment"],
        publication_handoff=artifacts["handoff"],
        publication_receipt=receipt,
        visibility_report=visibility,
    )
    assert len(memory["records"]) == 1
    assert memory["pending_candidates"] == []
    assert memory["status"] == "observation-complete"
    validate_artifact("strategy-memory", memory)


def test_strategy_early_stop_is_explicit_and_deterministic():
    assert early_stop([0.02, 0.0, -0.01], max_no_improvement=2)["stop"] is True
    assert early_stop([0.02, 0.01], max_no_improvement=2)["stop"] is False


def test_strategy_rejects_malformed_nested_input_as_value_error(tmp_path):
    payload = json.loads(FIXTURE.read_text())
    payload["metric_weights"] = [1.0]
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    try:
        strategy(invalid, tmp_path / "runs")
    except ValueError as exc:
        assert "metric weights" in str(exc)
    else:
        raise AssertionError("malformed nested strategy input was accepted")
