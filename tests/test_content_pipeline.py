from __future__ import annotations

import json
from pathlib import Path

from geo_seo_hub.content import content


FIXTURE = Path(__file__).parents[1] / "skills/geo-content/references/input-example.json"


def test_deterministic_pipeline_is_stable_and_binds_outline_to_claims(tmp_path):
    first = content(FIXTURE, tmp_path / "first", execution_mode="deterministic")
    second = content(FIXTURE, tmp_path / "second", execution_mode="deterministic")
    first_run = Path(first["output"])
    second_run = Path(second["output"])
    first_pipeline = json.loads((first_run / "content-pipeline.json").read_text())
    second_pipeline = json.loads((second_run / "content-pipeline.json").read_text())
    assert first_pipeline == second_pipeline
    assert first["semantic_digest"] == second["semantic_digest"]
    claim_ids = {item["claim_id"] for item in json.loads((first_run / "claim-map.json").read_text())["claims"]}
    assert all(set(section["claim_ids"]) <= claim_ids for section in first_pipeline["outline"])


def test_content_html_has_responsive_and_keyboard_focus_guards(tmp_path):
    result = content(FIXTURE, tmp_path / "runs", execution_mode="deterministic")
    html = (Path(result["output"]) / "content.html").read_text()
    assert "overflow-x:hidden" in html
    assert ":focus-visible" in html
    assert "overflow-x:auto" in html
    assert str(tmp_path) not in html


def test_provider_content_mode_falls_back_with_explicit_degradation(tmp_path):
    result = content(FIXTURE, tmp_path / "runs", execution_mode="provider")
    pipeline = json.loads((Path(result["output"]) / "content-pipeline.json").read_text())
    assert result["status"] == "completed-with-warnings"
    assert pipeline["execution"]["status"] == "degraded"
    assert pipeline["execution"]["failures"] == ["provider mode has no configured drafting adapter; deterministic pipeline completed"]

