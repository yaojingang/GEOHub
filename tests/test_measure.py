import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from geo_seo_hub.cli import main
from geo_seo_hub.measure import measure
from geo_seo_hub.validation import validate_artifact


FIXTURE = Path(__file__).parent / "fixtures" / "engine-observation-bundle.json"


def _clock():
    return datetime(2026, 8, 12, 8, 0, tzinfo=timezone.utc)


def test_measure_cli_writes_recomputable_visibility_report_without_network(tmp_path, capsys):
    with patch("socket.socket", side_effect=AssertionError("measure must remain offline")):
        assert main(["measure", "--input", str(FIXTURE), "--output", str(tmp_path / "runs")]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["observation_count"] == 20
    run = Path(payload["output"])
    report = json.loads((run / "visibility-report.json").read_text(encoding="utf-8"))
    validate_artifact("visibility-report", report)
    assert report["metrics"]["mention_rate"] == {
        "value": 0.6,
        "numerator": 12.0,
        "denominator": 20,
        "missing_count": 0,
    }
    assert report["metrics"]["source_inclusion_rate"]["value"] == 0.4
    assert report["metrics"]["citation_share"]["value"] == 0.5
    assert report["metrics"]["answer_coverage"]["value"] == 1.0
    assert report["metrics"]["observation_coverage"]["value"] == 1.0
    assert report["metrics"]["missing_observation_rate"]["value"] == 0.0
    assert set(report["by_engine"]) == {"openai", "perplexity"}
    assert len(report["query_components"]) == 20


def test_measure_semantic_digest_ignores_generation_time(tmp_path):
    first = measure(FIXTURE, tmp_path / "first", clock=_clock)
    second = measure(
        FIXTURE,
        tmp_path / "second",
        clock=lambda: datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    first_report = json.loads((Path(first["output"]) / "visibility-report.json").read_text())
    second_report = json.loads((Path(second["output"]) / "visibility-report.json").read_text())
    assert first_report["generated_at"] != second_report["generated_at"]
    assert first_report["semantic_digest"] == second_report["semantic_digest"]
    assert first_report["metrics"] == second_report["metrics"]


def test_measure_rejects_duplicate_observation_slot(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    duplicate = dict(payload["observations"][0])
    duplicate["observation_id"] = "duplicate-slot-new-id"
    payload["observations"].append(duplicate)
    invalid = tmp_path / "duplicate.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate observation slot"):
        measure(invalid, tmp_path / "runs", clock=_clock)


def test_measure_route_is_active_and_runnable(capsys):
    assert main(["route", "--text", "监测 AI 可见度"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["skill_id"] == "geo-measure"
    assert payload["status"] == "active"
    assert payload["runnable"] is True


def test_missing_observations_reduce_visibility_scores(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["observations"] = [payload["observations"][0]]
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps(payload), encoding="utf-8")
    result = measure(partial, tmp_path / "runs", clock=_clock)
    report = json.loads((Path(result["output"]) / "visibility-report.json").read_text())
    assert report["metrics"]["mention_rate"]["value"] == 0.05
    assert report["metrics"]["source_inclusion_rate"]["value"] == 0.05
    assert report["metrics"]["observation_coverage"]["value"] == 0.05


def test_measure_rejects_mixed_fixture_and_live_collection_methods(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["observations"][0]["collection_method"] = "manual_export"
    mixed = tmp_path / "mixed.json"
    mixed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot mix collection methods"):
        measure(mixed, tmp_path / "runs", clock=_clock)
