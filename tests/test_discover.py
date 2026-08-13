import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from geo_seo_hub.artifact_bus import ArtifactBus
from geo_seo_hub.discover import _build_query_map, discover
from geo_seo_hub.validation import ArtifactValidationError, validate_artifact

FIXTURES = Path(__file__).parent / "fixtures"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _clock():
    return datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def test_discover_happy_path_writes_valid_artifact_bus(tmp_path):
    runs_root = tmp_path / "runs"
    result = discover(FIXTURES / "brief.json", runs_root, clock=_clock)
    output = runs_root / result["run_id"]
    assert result["status"] == "completed"
    assert result["query_count"] == 4
    assert result["warning_count"] == 0
    assert Path(result["output"]) == output
    assert output.parent.name == "runs"
    assert output.name.startswith("run-")

    expected = {
        "input/geo-brief.json",
        "run-manifest.json",
        "evidence-ledger.json",
        "query-map.json",
        "opportunity-map.json",
        "quality-report.json",
        "run-lineage.json",
    }
    actual = {
        str(path.relative_to(output))
        for path in output.rglob("*.json")
    }
    assert actual == expected

    for filename, schema_name in {
        "run-manifest.json": "run-manifest",
        "evidence-ledger.json": "evidence-ledger",
        "query-map.json": "query-map",
        "opportunity-map.json": "opportunity-map",
        "quality-report.json": "quality-report",
        "run-lineage.json": "run-lineage",
    }.items():
        validate_artifact(schema_name, _load(output / filename))

    ledger = _load(output / "evidence-ledger.json")
    assert ledger["records"][0]["status"] == "provided"
    assert ledger["missing_evidence"] == []


def test_discover_records_missing_evidence_without_fabrication(tmp_path):
    runs_root = tmp_path / "runs"
    result = discover(FIXTURES / "brief-missing-evidence.json", runs_root, clock=_clock)
    output = runs_root / result["run_id"]
    ledger = _load(output / "evidence-ledger.json")
    report = _load(output / "quality-report.json")
    queries = _load(output / "query-map.json")["queries"]

    assert result["status"] == "completed-with-warnings"
    assert ledger["records"] == []
    assert len(ledger["missing_evidence"]) == 2
    assert report["status"] == "passed-with-warnings"
    assert "missing evidence" in report["warnings"][0]
    assert {item["evidence_status"] for item in queries} == {"missing"}


def test_discovery_content_is_deterministic(tmp_path):
    first_result = discover(FIXTURES / "brief.json", tmp_path / "first", clock=_clock)
    second_result = discover(
        FIXTURES / "brief.json",
        tmp_path / "second",
        clock=lambda: datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    first = Path(first_result["output"])
    second = Path(second_result["output"])
    for filename in ("query-map.json", "opportunity-map.json", "evidence-ledger.json"):
        assert _load(first / filename) == _load(second / filename)


def test_artifact_bus_rejects_nonempty_output_and_path_escape(tmp_path):
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "user-file.txt").write_text("preserve me", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        ArtifactBus(occupied)

    bus = ArtifactBus(tmp_path / "clean")
    with pytest.raises(ValueError, match="escapes run directory"):
        bus.write_json("../outside.json", {})


def test_artifact_bus_failure_is_invisible_and_retryable(tmp_path, monkeypatch):
    runs_root = tmp_path / "runs"
    original_write_json = ArtifactBus.write_json
    calls = 0

    def fail_midway(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("simulated staged write failure")
        return original_write_json(self, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(ArtifactBus, "write_json", fail_midway)
        with pytest.raises(RuntimeError, match="staged write failure"):
            discover(FIXTURES / "brief.json", runs_root, clock=_clock)

    assert runs_root.is_dir()
    assert list(runs_root.iterdir()) == []
    result = discover(FIXTURES / "brief.json", runs_root, clock=_clock)
    assert Path(result["output"]).is_dir()
    assert not any(path.name.startswith(".") for path in runs_root.iterdir())


def test_artifact_bus_concurrent_same_run_id_has_one_winner(tmp_path):
    runs_root = tmp_path / "runs"
    barrier = threading.Barrier(2)

    def publish(label):
        try:
            with ArtifactBus.transaction(runs_root, "run-concurrent") as bus:
                bus.write_text("payload.txt", label)
                bus.write_json(
                    "run-manifest.json",
                    {"artifacts": ["payload.txt"]},
                )
                barrier.wait(timeout=5)
                path = bus.publish({"payload.txt", "run-manifest.json"})
                return "ok", path
        except ValueError as exc:
            return "error", str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, ("first", "second")))

    assert [status for status, _value in results].count("ok") == 1
    assert [status for status, _value in results].count("error") == 1
    assert (runs_root / "run-concurrent" / "payload.txt").read_text() in {"first", "second"}
    assert not any(path.name.startswith(".run-") for path in runs_root.iterdir())


def test_discover_rejects_duplicate_evidence_ids(tmp_path):
    source = _load(FIXTURES / "brief.json")
    source["evidence"].append(dict(source["evidence"][0]))
    duplicate_brief = tmp_path / "duplicate.json"
    duplicate_brief.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        discover(duplicate_brief, tmp_path / "runs", clock=_clock)


def test_discover_rejects_blank_seed_before_normalization(tmp_path):
    source = _load(FIXTURES / "brief.json")
    source["seed_queries"] = ["   "]
    blank_brief = tmp_path / "blank.json"
    blank_brief.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="seed_queries"):
        discover(blank_brief, tmp_path / "runs", clock=_clock)


def test_query_builder_rejects_seed_empty_after_normalization():
    with pytest.raises(ValueError, match="non-blank seed"):
        _build_query_map(
            {
                "locale": "en",
                "seed_queries": [" ", "\t"],
                "audiences": ["buyer"],
                "scenarios": ["research"],
                "evidence": [],
            },
            "run-test",
        )
