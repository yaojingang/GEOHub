from __future__ import annotations

import json
from pathlib import Path

from geo_seo_hub.discover import discover
from geo_seo_hub.validation import validate_artifact


FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parents[1]


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_deterministic_v2_is_stable_and_exposes_score_components(tmp_path):
    first = discover(FIXTURES / "brief.json", tmp_path / "first", execution_mode="deterministic")
    second = discover(FIXTURES / "brief.json", tmp_path / "second", execution_mode="deterministic")
    first_query = _read(Path(first["output"]) / "query-map.json")
    second_query = _read(Path(second["output"]) / "query-map.json")
    first_opportunity = _read(Path(first["output"]) / "opportunity-map.json")
    second_opportunity = _read(Path(second["output"]) / "opportunity-map.json")

    assert first_query == second_query
    assert first_opportunity == second_opportunity
    assert first["semantic_digest"] == second["semantic_digest"]
    assert all(item["generator"] in {"template_baseline", "question_graph"} for item in first_query["queries"])
    assert all(0 <= item["novelty"] <= 1 for item in first_query["queries"])
    assert all(set(item["score_components"]) == {"coverage", "relevance", "novelty", "evidence", "business_fit"} for item in first_opportunity["opportunities"])
    validate_artifact("query-map", first_query)
    validate_artifact("opportunity-map", first_opportunity)


def test_v2_gold_label_coverage_improves_twenty_percent_and_duplicate_rate_is_bounded(tmp_path):
    gold = _read(ROOT / "evals/discovery/gold-labels.json")
    legacy = discover(FIXTURES / "brief.json", tmp_path / "legacy", execution_mode="legacy")
    modern = discover(FIXTURES / "brief.json", tmp_path / "modern", execution_mode="deterministic")
    legacy_map = _read(Path(legacy["output"]) / "query-map.json")
    modern_map = _read(Path(modern["output"]) / "query-map.json")

    def covered(payload):
        generators = {item.get("generator", "template_baseline") for item in payload["queries"]}
        intents = {item["intent"] for item in payload["queries"]}
        return sum(
            label["generator"] in generators and label["intent"] in intents
            for label in gold["labels"]
        )

    assert covered(modern_map) >= covered(legacy_map) * 1.2
    normalized = ["".join(item["question"].casefold().split()) for item in modern_map["queries"]]
    duplicate_rate = 1 - len(set(normalized)) / len(normalized)
    assert duplicate_rate < 0.10
    assert gold["review"]["required_annotators"] == 2
    assert gold["review"]["completed_annotators"] == 0
    assert gold["review"]["adjudication_status"] == "missing evidence"


def test_missing_evidence_never_increases_evidence_score(tmp_path):
    missing_brief = tmp_path / "missing.json"
    source = _read(FIXTURES / "brief.json")
    source["evidence"] = []
    missing_brief.write_text(json.dumps(source), encoding="utf-8")
    result = discover(missing_brief, tmp_path / "runs", execution_mode="deterministic")
    opportunities = _read(Path(result["output"]) / "opportunity-map.json")["opportunities"]
    assert all(item["evidence_status"] == "missing" for item in opportunities)
    assert all(item["score_components"]["evidence"] == 0 for item in opportunities)


def test_provider_unavailable_degrades_to_deterministic_baseline(tmp_path):
    result = discover(FIXTURES / "brief.json", tmp_path / "runs", execution_mode="provider")
    query_map = _read(Path(result["output"]) / "query-map.json")
    assert result["status"] == "completed-with-warnings"
    assert query_map["execution"]["status"] == "degraded"
    assert query_map["execution"]["failures"] == ["provider adapter unavailable; deterministic fallback completed"]
    assert query_map["queries"]
