from __future__ import annotations

import json
from pathlib import Path

import pytest

from geo_seo_hub.research import (
    build_research_context,
    load_research_registry,
    validate_research_registry,
)
from geo_seo_hub.validation import validate_artifact


EXPECTED_SOURCE_IDS = [f"P{index:02d}" for index in range(1, 55)] + ["D01", "D02"]


def test_research_registry_covers_the_frozen_corpus() -> None:
    registry = load_research_registry()

    assert registry["registry_version"] == "1.0.0"
    assert registry["source_commit"] == "90ad40cf059f300f23fd874353767e1d19ccb815"
    assert registry["source_ids"] == EXPECTED_SOURCE_IDS
    assert len(registry["principles"]) >= 8
    validate_research_registry(registry)
    validate_artifact("research-evidence-registry", registry)


def test_research_context_is_surface_scoped_and_source_resolved() -> None:
    context = build_research_context("run-example", "geo-discover")

    validate_artifact("research-context", context)
    assert context["protocol_version"] == "1.0.0"
    assert context["surface"] == "geo-discover"
    assert context["registry_version"] == "1.0.0"
    assert context["principles"]
    assert any(item["principle_id"] == "query-diversity-is-conditional" for item in context["principles"])
    assert all("geo-discover" in item["surfaces"] or "all" in item["surfaces"] for item in context["principles"])
    assert all(item["source_ids"] for item in context["principles"])
    assert all(item["causal_status"] for item in context["principles"])
    assert all(item["platform_scope"] for item in context["principles"])
    assert all(item["limitations"] for item in context["principles"])
    assert set(context["applied_source_ids"]) <= set(EXPECTED_SOURCE_IDS)
    assert context["effect_guarantee"] is False


def test_research_registry_rejects_unknown_sources_and_effect_guarantees() -> None:
    registry = json.loads(json.dumps(load_research_registry()))
    registry["principles"][0]["source_ids"].append("P99")
    with pytest.raises(ValueError, match="unknown research source"):
        validate_research_registry(registry)

    registry = json.loads(json.dumps(load_research_registry()))
    registry["principles"][0]["allowed_use"] = "effect-guarantee"
    with pytest.raises(ValueError, match="effect guarantees"):
        validate_research_registry(registry)


def test_research_context_schema_is_installed_as_package_data() -> None:
    project = Path(__file__).parents[1] / "pyproject.toml"
    text = project.read_text(encoding="utf-8")

    assert '"registry/research-evidence.json"' in text
    assert '"schemas/research-context.schema.json"' in text
    assert '"schemas/research-evidence-registry.schema.json"' in text
