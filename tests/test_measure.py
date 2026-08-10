import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from geo_seo_hub.measure import measure
from geo_seo_hub.validation import ArtifactValidationError, validate_artifact


FIXTURE = Path(__file__).parent / "fixtures" / "measurement-brief.json"


def _clock():
    return datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_measure_preserves_denominators_missing_answers_and_lineage(tmp_path):
    result = measure(FIXTURE, tmp_path / "runs", clock=_clock)
    run = Path(result["output"])

    assert result == {
        "run_id": result["run_id"],
        "status": "completed-with-warnings",
        "output": str(run),
        "trial_count": 3,
        "eligible_trial_count": 2,
        "warning_count": 2,
    }
    report = _read(run / "measurement-report.json")
    assert report["effect_guarantee"] is False
    assert report["causal_status"] == "descriptive"
    assert report["trial_count"] == 3
    assert report["eligible_trial_count"] == 2
    assert report["answered_count"] == 1
    assert report["missing_answer_count"] == 1
    assert report["excluded_count"] == 1
    assert report["missing_answer_reasons"] == {"empty-response": 1}
    assert report["exclusion_reasons"] == {"transport-failure": 1}
    assert report["metrics"]["citation_rate"] == {
        "numerator": 1,
        "denominator": 2,
        "estimate": 0.5,
        "interval_lower": pytest.approx(0.0945312057),
        "interval_upper": pytest.approx(0.9054687943),
        "interval_method": "wilson-score",
    }
    assert report["metrics"]["conditional_citation_rate"]["denominator"] == 1
    assert len(report["platform_strata"]) == 1
    assert report["platform_strata"][0]["interface"] == "web"

    ledger = _read(run / "evidence-ledger.json")
    assert len(ledger["records"]) == 3
    assert {record["source_uri"] for record in ledger["records"]} == {
        "urn:geo-measure:trial-001",
        "urn:geo-measure:trial-002",
        "urn:geo-measure:trial-003",
    }
    research = _read(run / "research-context.json")
    assert research["surface"] == "geo-measure"
    assert "measurement-requires-distributions-and-denominators" in {
        item["principle_id"] for item in research["principles"]
    }

    expected = {
        "input/measurement-brief.json",
        "measurement-report.json",
        "report.md",
        "evidence-ledger.json",
        "research-context.json",
        "quality-report.json",
        "run-manifest.json",
    }
    assert {path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file()} == expected
    manifest = _read(run / "run-manifest.json")
    assert set(manifest["artifacts"]) == expected - {"run-manifest.json"}
    for filename, schema_name in {
        "input/measurement-brief.json": "measurement-brief",
        "measurement-report.json": "measurement-report",
        "evidence-ledger.json": "evidence-ledger",
        "research-context.json": "research-context",
        "quality-report.json": "quality-report",
        "run-manifest.json": "run-manifest",
    }.items():
        validate_artifact(schema_name, _read(run / filename))


def test_measure_is_deterministic_except_manifest_time(tmp_path):
    first = Path(measure(FIXTURE, tmp_path / "first", clock=_clock)["output"])
    second = Path(
        measure(
            FIXTURE,
            tmp_path / "second",
            clock=lambda: datetime(2027, 1, 1, tzinfo=timezone.utc),
        )["output"]
    )
    for filename in (
        "input/measurement-brief.json",
        "measurement-report.json",
        "evidence-ledger.json",
        "research-context.json",
        "quality-report.json",
    ):
        assert _read(first / filename) == _read(second / filename)


def test_measure_rejects_no_eligible_trials(tmp_path):
    payload = _read(FIXTURE)
    for observation in payload["observations"]:
        observation["eligible"] = False
        observation["answered"] = False
        observation["cited"] = None
        observation["missing_answer_reason"] = None
        observation["exclusion_reason"] = "out-of-scope"
    brief = tmp_path / "none-eligible.json"
    brief.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="at least one eligible trial"):
        measure(brief, tmp_path / "runs", clock=_clock)


def test_measure_rejects_duplicate_trials_and_invalid_answer_states(tmp_path):
    payload = _read(FIXTURE)
    payload["observations"].append(dict(payload["observations"][0]))
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate trial_id"):
        measure(duplicate, tmp_path / "duplicate-runs", clock=_clock)

    invalid_payload = _read(FIXTURE)
    invalid_payload["observations"][1]["cited"] = True
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(invalid_payload), encoding="utf-8")
    with pytest.raises(ArtifactValidationError):
        measure(invalid, tmp_path / "invalid-runs", clock=_clock)


def test_measure_rejects_nonfinite_json(tmp_path):
    text = FIXTURE.read_text(encoding="utf-8").replace('"confidence_level": 0.95', '"confidence_level": 1e9999')
    brief = tmp_path / "nonfinite.json"
    brief.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        measure(brief, tmp_path / "runs", clock=_clock)
