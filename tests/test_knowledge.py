import json
from datetime import datetime, timezone
from pathlib import Path

from geo_seo_hub.intelligence.knowledge import build_knowledge_graph, query_knowledge_graph
from geo_seo_hub.knowledge import knowledge
from geo_seo_hub.validation import validate_artifact


FIXTURE = Path(__file__).parent / "fixtures" / "knowledge-request.json"


def test_knowledge_preserves_conflicts_and_source_lineage(tmp_path):
    result = knowledge(
        FIXTURE,
        tmp_path / "runs",
        clock=lambda: datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    run = Path(result["output"])
    graph = json.loads((run / "knowledge-graph.json").read_text())
    validate_artifact("knowledge-graph", graph)
    assert graph["coverage"]["source_coverage"] == 1.0
    assert len(graph["conflicts"]) == 1
    assert {fact["value"] for fact in graph["entities"][0]["facts"]} == {"managed", "hybrid"}
    assert graph["relations"][0]["source_ids"] == ["product-page"]
    assert result["evidence_status"] == "provided"


def test_knowledge_supports_local_and_global_queries():
    request = json.loads(FIXTURE.read_text())
    graph = build_knowledge_graph(request)
    local = query_knowledge_graph(graph, {"mode": "local", "value": "Acme GEO"})
    global_result = query_knowledge_graph(graph, {"mode": "global", "value": "coverage"})
    assert local["entities"]
    assert local["relations"]
    assert global_result["communities"]
    assert global_result["coverage"] == graph["coverage"]


def test_knowledge_incremental_update_uses_source_hash_and_identity():
    request = json.loads(FIXTURE.read_text())
    first = build_knowledge_graph(request)
    same = build_knowledge_graph(request, existing_graph=first)
    assert same["semantic_digest"] == first["semantic_digest"]
    request["sources"][0]["source_hash"] = "c" * 64
    request["sources"][0]["facts"][0]["value"] = "private cloud"
    changed = build_knowledge_graph(request, existing_graph=first)
    entity = next(item for item in changed["entities"] if item["canonical_name"] == "Acme GEO")
    assert "private cloud" in {fact["value"] for fact in entity["facts"]}
    assert "managed" not in {fact["value"] for fact in entity["facts"]}


def test_knowledge_rejects_same_hash_payload_drift_and_delta_source_loss():
    request = json.loads(FIXTURE.read_text())
    first = build_knowledge_graph(request)
    changed = json.loads(FIXTURE.read_text())
    changed["sources"][0]["facts"][0]["value"] = "changed without hash"
    try:
        build_knowledge_graph(changed, existing_graph=first)
    except ValueError as exc:
        assert "without a new source hash" in str(exc)
    else:
        raise AssertionError("same-hash payload drift was accepted")

    delta = json.loads(FIXTURE.read_text())
    delta["sources"] = delta["sources"][:1]
    try:
        build_knowledge_graph(delta, existing_graph=first)
    except ValueError as exc:
        assert "full source snapshot" in str(exc)
    else:
        raise AssertionError("partial delta discarded existing sources")


def test_knowledge_rejects_malformed_nested_input_as_value_error(tmp_path):
    request = json.loads(FIXTURE.read_text())
    request["sources"][0]["relations"][0]["confidence"] = "high"
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(request), encoding="utf-8")
    try:
        knowledge(invalid, tmp_path / "runs")
    except ValueError as exc:
        assert "confidence" in str(exc)
    else:
        raise AssertionError("malformed nested knowledge input was accepted")
